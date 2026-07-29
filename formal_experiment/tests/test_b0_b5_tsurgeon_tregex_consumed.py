"""Synthetic-only gates for B5 genuine Tsurgeon/Tregex consumption.

These tests use hand-written constituency trees and neutral toy text.  They do
not load EStG-150 Gold, error lists, sample identities, Independent-82, or the
S2.4 test split.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bpc_hybrid.b0_v10.actor_action_tregex_b5 import (  # noqa: E402
    extract_actors_actions_edges_b5,
)
from bpc_hybrid.estg150_b0_development import (  # noqa: E402
    Estg150B0DevelopmentError,
    sha256_file,
)
from bpc_hybrid.estg150_b0_development_b5 import (  # noqa: E402
    BRIDGE_CLASS,
    BRIDGE_REL,
    PARENT_REGISTRY_SHA256,
    REGISTRY_REL,
    align_de_to_en_units as b5_align,
    collect_classifier_inputs as b5_collect_classifier_inputs,
    parse_bridge_output_b5,
    plan_clause_units_v4 as b5_plan_clause_units,
    resolve_modality_v10 as b5_resolve_modality,
    validate_b5_registry,
    write_b5_rule_plan,
)
from bpc_hybrid.estg150_b0_development_v10 import (  # noqa: E402
    align_de_to_en_units as v10_align,
    collect_classifier_inputs as v10_collect_classifier_inputs,
    plan_clause_units_v4 as v10_plan_clause_units,
    resolve_modality_v10 as v10_resolve_modality,
)
from bpc_hybrid.sun_style.corenlp_runtime import resolve_corenlp_runtime  # noqa: E402
from bpc_hybrid.sun_style.lexicon_v2_runtime import load_lexicon_v2  # noqa: E402


FIXTURE = ROOT / "tests/fixtures/corenlp/b5_tsurgeon_synthetic_v1.json"
RUNTIME_HOME = Path(r"D:\environment\stanford-corenlp-4.5.10")


@pytest.fixture(scope="module")
def bridge_result(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    javac = shutil.which("javac")
    probe = resolve_corenlp_runtime(ROOT, home=RUNTIME_HOME)
    if not javac or not probe.ready or not probe.java_executable:
        pytest.skip("local CoreNLP 4.5.10 Java runtime is unavailable")
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    work = tmp_path_factory.mktemp("b5_utf8_bridge")
    classes = work / "classes"
    classes.mkdir()
    plan = work / "plan.tsv"
    proof = write_b5_rule_plan(ROOT, plan)
    trees = work / "trees.txt"
    trees.write_text(
        "\n".join(case["tree"] for case in fixture["cases"]) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    classpath = os.pathsep.join(probe.classpath_entries)
    compile_run = subprocess.run(
        [
            javac,
            "--release",
            "8",
            "-Xlint:-options",
            "-encoding",
            "UTF-8",
            "-cp",
            classpath,
            "-d",
            str(classes),
            str(ROOT / BRIDGE_REL),
        ],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="strict",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert compile_run.returncode == 0, compile_run.stderr
    bridge_classpath = os.pathsep.join((str(classes), classpath))
    run = subprocess.run(
        [
            probe.java_executable,
            "-Dfile.encoding=UTF-8",
            "-cp",
            bridge_classpath,
            BRIDGE_CLASS,
            str(plan),
            str(trees),
        ],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="strict",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert run.returncode == 0, run.stderr
    cases, summary = parse_bridge_output_b5(run.stdout)
    return {
        "fixture": fixture,
        "proof": proof,
        "raw": run.stdout,
        "cases": cases,
        "summary": summary,
    }


def _fields(result: dict[str, Any], case_id: str) -> dict[str, list[dict[str, Any]]]:
    ids = [case["id"] for case in result["fixture"]["cases"]]
    return result["cases"][ids.index(case_id)]["fields"]


def test_gate_01_condition_sbar_pruned_main_action_survives(bridge_result: dict[str, Any]) -> None:
    fields = _fields(bridge_result, "condition_sbar")
    assert fields["condition"][0]["operation_applied"] is True
    assert fields["action"] and fields["action"][0]["phase"] == "post_surgery"


def test_gate_02_temporal_constraint_pp_pruned_main_action_survives(bridge_result: dict[str, Any]) -> None:
    fields = _fields(bridge_result, "temporal_constraint_pp")
    assert fields["constraint"][0]["text"] == "within thirty days"
    assert fields["constraint"][0]["operation_applied"] is True
    assert fields["action"][0]["text"] == "issue a notice"


def test_gate_03_quantitative_np_pruned_main_action_survives(bridge_result: dict[str, Any]) -> None:
    fields = _fields(bridge_result, "quantitative_constraint_np")
    assert fields["constraint"][0]["text"] == "no later than thirty days"
    assert fields["constraint"][0]["operation_applied"] is True
    assert fields["action"][0]["text"] == "issue a notice"


def test_gate_04_exception_pp_pruned_main_action_survives(bridge_result: dict[str, Any]) -> None:
    fields = _fields(bridge_result, "exception_pp")
    assert fields["exception"][0]["operation_applied"] is True
    assert fields["action"][0]["text"] == "issue a notice"


def test_gate_05_does_not_apply_is_nondestructive(bridge_result: dict[str, Any]) -> None:
    fields = _fields(bridge_result, "does_not_apply_nondestructive")
    assert fields["exception"][0]["pattern_index"] == 4
    assert fields["exception"][0]["operation_applied"] is False
    assert fields["exception"][0]["surgery_status"] == "none"


def test_gate_06_whole_tree_prune_is_rejected_and_restored(bridge_result: dict[str, Any]) -> None:
    fields = _fields(bridge_result, "whole_tree_rejection")
    condition = fields["condition"][0]
    assert condition["operation_applied"] is False
    assert condition["surgery_status"] == "rejected_null"
    # A later post-surgery action match proves the rejected tree was restored.
    assert fields["action"][0]["text"] == "acts"
    assert "FINAL\t5\t(SBAR" in bridge_result["raw"]


def test_gate_07_duplicate_tokens_preserve_original_identity(bridge_result: dict[str, Any]) -> None:
    fields = _fields(bridge_result, "duplicate_token_identity")
    assert fields["constraint"][0]["token_runs"] == "5-8"
    assert fields["action"][0]["token_runs"] == "2-5,8-10"


def test_gate_08_discontinuous_action_runs_are_not_enveloped(bridge_result: dict[str, Any]) -> None:
    fields = _fields(bridge_result, "discontinuous_action_runs")
    action = fields["action"][0]
    assert action["begin"] == 2 and action["end"] == 8
    assert action["token_runs"] == "2-3,6-8"
    assert "3-6" not in action["token_runs"]


def _toy_sentence() -> tuple[str, dict[str, Any]]:
    text = "The authority issues the notice"
    words = [("The", "DT"), ("authority", "NN"), ("issues", "VBZ"), ("the", "DT"), ("notice", "NN")]
    tokens = []
    cursor = 0
    for index, (word, pos) in enumerate(words, start=1):
        start = text.index(word, cursor)
        end = start + len(word)
        tokens.append(
            {
                "index": index,
                "word": word,
                "originalText": word,
                "pos": pos,
                "characterOffsetBegin": start,
                "characterOffsetEnd": end,
            }
        )
        cursor = end
    sentence = {
        "tokens": tokens,
        "basicDependencies": [
            {"dep": "ROOT", "governor": 0, "dependent": 3},
            {"dep": "nsubj", "governor": 3, "dependent": 2},
            {"dep": "det", "governor": 2, "dependent": 1},
            {"dep": "obj", "governor": 3, "dependent": 5},
            {"dep": "det", "governor": 5, "dependent": 4},
        ],
    }
    return text, sentence


def test_gate_09_final_actor_action_route_is_post_surgery_tregex() -> None:
    text, sentence = _toy_sentence()
    actors, actions, edges, stats = extract_actors_actions_edges_b5(
        sentence=sentence,
        source_text=text,
        clause_start=0,
        clause_end=len(text),
        sentence_index=0,
        lexicon=load_lexicon_v2(ROOT),
        action_observations=[
            {"begin": 2, "end": 5, "pattern_index": 0, "phase": "post_surgery", "token_runs": "2-5"}
        ],
        actor_observations=[
            {"begin": 0, "end": 2, "pattern_index": 0, "phase": "post_surgery", "token_runs": "0-2"}
        ],
    )
    assert actors[0]["route"] == "post_surgery_tregex"
    assert actions[0]["route"] == "post_surgery_tregex"
    assert text[actors[0]["start"] : actors[0]["end"]] == actors[0]["text"]
    assert text[actions[0]["start"] : actions[0]["end"]] == actions[0]["text"]
    assert edges and stats["final_tregex_actor_spans"] == 1
    assert stats["final_tregex_action_spans"] == 1


def test_gate_10_dependency_candidate_and_fallback_are_zero() -> None:
    text, sentence = _toy_sentence()
    actors, actions, edges, stats = extract_actors_actions_edges_b5(
        sentence=sentence,
        source_text=text,
        clause_start=0,
        clause_end=len(text),
        sentence_index=0,
        lexicon=load_lexicon_v2(ROOT),
        action_observations=[],
        actor_observations=[],
    )
    assert (actors, actions, edges) == ([], [], [])
    assert stats["dependency_candidate_span_count"] == 0
    assert stats["dependency_fallback_count"] == 0


def test_gate_11_windows_subprocess_is_utf8(bridge_result: dict[str, Any]) -> None:
    fields = _fields(bridge_result, "windows_utf8")
    assert fields["actor"][0]["text"] == "The Ärztin"
    assert "Ärztin" in bridge_result["raw"]


def test_gate_12_malformed_bridge_output_fails_closed(bridge_result: dict[str, Any]) -> None:
    malformed = bridge_result["raw"].replace("SUMMARY\t9\t29\t29\t6", "SUMMARY\t9\t28\t29\t6")
    with pytest.raises(Estg150B0DevelopmentError):
        parse_bridge_output_b5(malformed)


def test_gate_13_exact_29_pattern_identity_order_and_operation_mapping() -> None:
    proof = validate_b5_registry(ROOT)
    assert proof["parent_pattern_count"] == proof["candidate_pattern_count"] == 29
    assert proof["pattern_strings_exact_parent"] is True
    assert proof["pattern_order_exact_parent"] is True
    assert proof["only_operation_metadata_changed"] is True
    assert proof["parent_registry_sha256"] == PARENT_REGISTRY_SHA256
    assert sha256_file(ROOT / REGISTRY_REL) == proof["candidate_registry_sha256"]


def test_gate_14_b4_lexicon_is_not_loaded() -> None:
    runtime = load_lexicon_v2(ROOT)
    source = (ROOT / "src/bpc_hybrid/estg150_b0_development_b5.py").read_text(encoding="utf-8")
    assert runtime.manifest_sha256 == "3f7e6108c1e66de37377abc2e9b9f4d0344ff2d1eca20b49ebf90e38aff7b462"
    assert "public_marker_lexicon_en_v3_b4" not in source
    assert "estg150_b0_development_b4" not in source


def test_gate_15_v10_modality_segmentation_and_classifier_routes_are_shared() -> None:
    assert b5_resolve_modality is v10_resolve_modality
    assert b5_plan_clause_units is v10_plan_clause_units
    assert b5_collect_classifier_inputs is v10_collect_classifier_inputs
    assert b5_align is v10_align
