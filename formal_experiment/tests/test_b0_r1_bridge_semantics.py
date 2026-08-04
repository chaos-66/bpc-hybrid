"""B0-R1-BRIDGE: Tregex relation-operator and multi-match consumption tests.

Three layers:

1. Registry semantics (pure Python, no runtime): the active v3-enhanced
   registry deliberately uses both ``<`` (child) and ``<<`` (descendant)
   relations, and the distinction is structural (child patterns never
   accidentally match deeper descendants).

2. Bridge behavior (needs the local CoreNLP 4.5.10 runtime + javac; skipped
   when unavailable): ``<`` matches only direct children while ``<<`` matches
   any descendant; a pattern matching several disjoint nodes produces one
   MATCH per node when no operation is attached.

3. B0-R1-BRIDGE fail-closed guard: an operated rule (Tsurgeon operation
   attached) must match exactly one node.  ``Tsurgeon.processPattern`` applies
   the operation to every pattern match while the bridge records only one
   match, so a multi-match operated rule now fails closed instead of silently
   consuming unrecorded matches.
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
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from bpc_hybrid.sun_style.corenlp_runtime import resolve_corenlp_runtime  # noqa: E402

BRIDGE_SOURCE = ROOT / "tools/corenlp/SunPhraseRuleBatchBridgeMulti.java"


def _probe() -> Any:
    home = os.environ.get("CORENLP_HOME") or r"D:\environment\stanford-corenlp-4.5.10"
    return resolve_corenlp_runtime(ROOT, home=home)


def _compile_bridge(classpath: str, classes_dir: Path) -> None:
    javac = shutil.which("javac")
    assert javac, "javac is required for the bridge test"
    subprocess.run(
        [
            javac,
            "--release",
            "8",
            "-encoding",
            "UTF-8",
            "-cp",
            classpath,
            "-d",
            str(classes_dir),
            str(BRIDGE_SOURCE),
        ],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=300,
    )


def run_bridge(
    probe: Any,
    plans: list[tuple[str, str, str]],
    trees: list[str],
    work_dir: Path,
) -> subprocess.CompletedProcess[str]:
    """Compile and run the Multi bridge over synthetic trees."""
    classes_dir = work_dir / "classes"
    classes_dir.mkdir(exist_ok=True)
    classpath = os.pathsep.join(probe.classpath_entries)
    _compile_bridge(classpath, classes_dir)
    plan_path = work_dir / "plan.tsv"
    plan_path.write_text(
        "\n".join("\t".join(parts) for parts in plans) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    tree_path = work_dir / "trees.txt"
    tree_path.write_text("\n".join(trees) + "\n", encoding="utf-8", newline="\n")
    return subprocess.run(
        [
            probe.java_executable,
            "-cp",
            os.pathsep.join((str(classes_dir), classpath)),
            "SunPhraseRuleBatchBridgeMulti",
            str(plan_path),
            str(tree_path),
        ],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        encoding="utf-8",
        errors="replace",
        timeout=600,
    )


def match_lines(output: str) -> list[str]:
    return [line for line in output.splitlines() if line.startswith("MATCH\t")]


def match_texts(output: str) -> list[str]:
    texts: list[str] = []
    for line in match_lines(output):
        parts = line.split("\t")
        if len(parts) >= 6:
            texts.append(parts[5])
    return texts


def test_registry_uses_child_and_descendant_relations_deliberately() -> None:
    registry = json.loads(
        (ROOT / "resources/corenlp/sun_phrase_patterns_v3_enhanced.json").read_text(
            encoding="utf-8"
        )
    )
    child_uses = 0
    descendant_uses = 0
    for field in registry["fields"]:
        for pattern in field["tregex_patterns"]:
            if "<<" in pattern:
                descendant_uses += 1
            elif "<" in pattern:
                child_uses += 1
    assert child_uses >= 2
    assert descendant_uses >= 10
    # the registry declares the overlap-resolution contract
    assert registry["ordering_policy"]["overlap_resolution"] == "smallest_sufficient_then_leftmost"


@pytest.fixture(scope="module")
def probe() -> Any:
    probe = _probe()
    if not probe.ready or not probe.java_executable or not shutil.which("javac"):
        pytest.skip(f"CoreNLP runtime or javac unavailable: {probe.reasons}")
    return probe


@pytest.fixture()
def work_dir(tmp_path: Path) -> Path:
    return tmp_path


def test_child_relation_does_not_match_deeper_cue(probe: Any, work_dir: Path) -> None:
    # the word "shall" sits below the MD preterminal, so it is a descendant,
    # not a direct child, of the VP: the child relation must NOT match, the
    # descendant relation must.
    tree = "(ROOT (VP (MD shall) (NP (NN A))))"
    result = run_bridge(probe, [("modality", "VP=modality < shall", "")], [tree], work_dir)
    assert result.returncode == 0, result.stderr
    assert match_lines(result.stdout) == []
    result = run_bridge(probe, [("modality", "VP=modality << shall", "")], [tree], work_dir)
    assert result.returncode == 0, result.stderr
    assert len(match_lines(result.stdout)) == 1


def test_child_relation_matches_direct_child_cue(probe: Any, work_dir: Path) -> None:
    # the word is a direct child of the MD preterminal: the child relation
    # between the POS node and its word leaf matches (the registry's real
    # usage, e.g. "/^(MD|VB|VBP|VBZ)$/=modality < shall").
    tree = "(ROOT (VP (MD shall) (NP (NN A))))"
    result = run_bridge(probe, [("modality", "MD=modality < shall", "")], [tree], work_dir)
    assert result.returncode == 0, result.stderr
    assert len(match_lines(result.stdout)) == 1


def test_multi_match_no_operation_records_every_match(probe: Any, work_dir: Path) -> None:
    tree = "(ROOT (S (NP (NN A)) (VP (VB B) (NP (NN C)))))"
    result = run_bridge(
        probe,
        [("action", "NP=action << NN", "")],
        [tree],
        work_dir,
    )
    assert result.returncode == 0, result.stderr
    texts = match_texts(result.stdout)
    assert sorted(texts) == ["A", "C"], texts


def test_operated_rule_single_match_applies(probe: Any, work_dir: Path) -> None:
    tree = "(ROOT (NP (NN A)))"
    result = run_bridge(
        probe,
        [("action", "NP=action << NN", "delete action")],
        [tree],
        work_dir,
    )
    assert result.returncode == 0, result.stderr
    assert len(match_lines(result.stdout)) == 1


def test_operated_rule_multi_match_fails_closed(probe: Any, work_dir: Path) -> None:
    tree = "(ROOT (S (NP (NN A)) (VP (VB B) (NP (NN C)))))"
    result = run_bridge(
        probe,
        [("action", "NP=action << NN", "delete action")],
        [tree],
        work_dir,
    )
    assert result.returncode != 0
    assert "operated Tregex rule matched 2 nodes" in result.stderr
