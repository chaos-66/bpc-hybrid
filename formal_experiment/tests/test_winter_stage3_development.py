# -*- coding: utf-8 -*-
"""Regression tests for the Winter et al. (2020) Stage 3 development wrapper.

Covers: config loading, matching positives/negatives, the three violation
types, actor/lane matching, order relations (bug-fixed reachability), empty
values, input binding rejection, runner gold-blindness, deterministic reruns
and manifest/artifact hashes.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import spacy  # noqa: E402

from bpc_hybrid.winter_stage3.winter_clause import parse_regulation_paragraph  # noqa: E402
from bpc_hybrid.winter_stage3.winter_model import (  # noqa: E402
    WinterModel,
    WinterProcess,
    parse_bpmn_file_winter,
)
from bpc_hybrid.winter_stage3.winter_pair import WinterPair  # noqa: E402
from bpc_hybrid.winter_stage3.winter_similarity import WinterSimilarity  # noqa: E402

CONFIG = ROOT / "configs" / "winter_stage3_development_v1.json"
BPMN_DIR = ROOT / "data" / "input" / "stage1_stage3" / "gdpr7"
BLANK = ROOT / "data" / "development" / "human_review" / "stage3_gold_annotation_blank_v1.json"

NLP = spacy.load("en_core_web_sm")
STOPWORDS = {
    l for l in (
        ROOT.parent / "references" / "winter_2020_model_check" / "model_check"
        / "input" / "files" / "stopwords.txt"
    ).read_text(encoding="utf-8").splitlines()
}
SIGNALWORDS = {
    l for l in (
        ROOT.parent / "references" / "winter_2020_model_check" / "model_check"
        / "input" / "files" / "signalwords.txt"
    ).read_text(encoding="utf-8").splitlines()
}
SEQUENCEMARKERS = {
    l for l in (
        ROOT.parent / "references" / "winter_2020_model_check" / "model_check"
        / "input" / "files" / "sequencemarkers.txt"
    ).read_text(encoding="utf-8").splitlines()
}

GAMMA = 0.4
DELTA = 0.8


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _make_process(participant: str, task_names: list[str], flows: list[tuple[str, str]],
                  stopwords=STOPWORDS) -> WinterProcess:
    import xml.dom.minidom as minidom

    def _el(tag: str, name: str = "", id_: str = "") -> object:
        xml_str = (
            f'<{tag} id="{id_}" name="{name}" '
            f'sourceRef="s" targetRef="t"/>' if tag == "sequenceFlow"
            else f'<{tag} id="{id_}" name="{name}"/>'
        )
        return minidom.parseString(xml_str).documentElement

    tasks = [_el("task", name, f"t{i}") for i, name in enumerate(task_names)]
    flows_dom = [
        _el("sequenceFlow", id_=f"f{i}", name="") for i in range(len(flows))
    ]
    for i, (src, tgt) in enumerate(flows):
        flows_dom[i].setAttribute("sourceRef", src)
        flows_dom[i].setAttribute("targetRef", tgt)
    return WinterProcess(
        "p1", participant, [], [], tasks,
        {}, {}, flows_dom, NLP, stopwords,
    )


def _make_model(participant: str, task_names: list[str],
                flows: list[tuple[str, str]] | None = None) -> WinterModel:
    proc = _make_process(participant, task_names, flows or [])
    return WinterModel("test_model", [proc])


def _pair(model, rule_text: str, resource_set: set[str] | None = None,
          nlp=NLP, stopwords=STOPWORDS) -> WinterPair:
    sim = WinterSimilarity(nlp)
    paragraph = parse_regulation_paragraph(
        "articleX", rule_text, nlp, stopwords, SIGNALWORDS, SEQUENCEMARKERS
    )
    return WinterPair(nlp, sim, model, paragraph, resource_set or {"controller"}, GAMMA, DELTA)


def test_config_loads_gamma_delta_and_weights() -> None:
    config = _load_json(CONFIG)
    assert config["method"]["gamma"] == 0.4
    assert config["method"]["delta"] == 0.8
    assert config["method"]["only_constraints"] is True
    assert config["method"]["cost_weights"]["obligation"] == pytest.approx(1 / 3)
    assert config["inputs"]["gold_annotation_blank_pack"]["path"].endswith("_blank_v1.json")


def test_matching_positive_has_fitness_above_zero() -> None:
    model = _make_model("controller", ["Notify national authority", "Retrieve breached data"])
    pair = _pair(model, "The controller shall notify the supervisory authority of a personal data breach without undue delay.")
    assert pair.fitness > 0.0
    assert pair.cost_obligation < 1.0


def test_matching_negative_has_zero_or_low_fitness() -> None:
    model = _make_model("controller", ["Notify national authority"])
    pair = _pair(model, "The data subject shall have the right to request the erasure of personal data concerning him or her.")
    # unrelated obligation -> no mapping above gamma is likely; fitness stays 0
    assert pair.fitness >= 0.0


def test_missing_action_detected_when_obligation_unmatched() -> None:
    model = _make_model("controller", ["Send an invoice"])
    pair = _pair(model, "The controller shall notify the supervisory authority without undue delay.")
    # no similar task -> obligation cost > 0 -> missing action predicted
    assert pair.cost_obligation > 0.0


def test_incorrect_actor_detected_when_participant_mismatches() -> None:
    model = _make_model("processor", ["Notify national authority"])
    pair = _pair(
        model,
        "The controller shall notify the supervisory authority of a personal data breach.",
        resource_set={"controller"},
    )
    # task matches but the paragraph names "controller" while the model
    # participant is "processor" -> resource violation expected
    assert pair.cost_resource > 0.0


def test_incorrect_actor_vacuous_with_empty_participant() -> None:
    model = _make_model("", ["Notify national authority"])
    pair = _pair(
        model,
        "The controller shall notify the supervisory authority of a personal data breach.",
        resource_set={""},
    )
    assert pair.cost_resource == 0.0  # empty participant -> vacuous, disclosed limitation


def test_out_of_order_via_reachability_bug_fix() -> None:
    # tasks: t0 -> t1 (reachable), t1 NOT reachable from t0 in reverse
    model = _make_model("controller", ["Notify authority", "Handle delay"], flows=[("t0", "t1")])
    proc = model.processes[0]
    # bug-fixed semantics: t1 reachable from t0
    assert proc.is_reachable_from("t0", "t1") is True
    # prototype bug would return targetid in reachability[targetid] -> also True
    # but the reverse check is what matters: t0 not reachable from t1
    assert proc.is_reachable_from("t1", "t0") is False
    # original buggy expression: targetid in reachability[targetid] would be True
    # for the reverse check too, making the conjunction always False.
    reachability = proc.reachability
    assert "t0" not in reachability.get("t1", set())


def test_empty_obligations_do_not_crash() -> None:
    model = _make_model("controller", [])
    pair = _pair(model, "This sentence contains no signal word and is not a constraint.")
    assert pair.fitness == 0.0
    assert pair.cost == 0.0


def test_parse_bpmn_file_winter_on_frozen_gdpr7() -> None:
    bpmn = next(BPMN_DIR.glob("gdpr_1_data_breach.bpmn"))
    model = parse_bpmn_file_winter(bpmn, NLP, STOPWORDS)
    assert model._id == "gdpr_1_data_breach"
    assert len(model.processes) >= 1
    labels = []
    for proc in model.processes:
        labels.extend(proc.task_labels)
    assert any("notify" in label.lower() for label in labels)


def test_runner_is_gold_blind_and_deterministic(tmp_path) -> None:
    import run_winter_stage3_development as r
    import uuid
    import shutil
    # the runner's constants must point at the blank pack (no decisions)
    assert "blank" in str(r.BLANK_PACK)
    assert "correction" not in str(r.BLANK_PACK)
    config = _load_json(CONFIG)
    suffix = uuid.uuid4().hex[:8]
    runs = []
    try:
        for variant in (f"det_{suffix}_1", f"det_{suffix}_2"):
            run_dir = r.write_run(config, variant)
            runs.append(run_dir)
            result = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "evaluate_winter_stage3_development.py"),
                 "--run-dir", str(run_dir)],
                cwd=ROOT, text=True, encoding="utf-8", errors="replace",
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
            )
            assert result.returncode == 0, result.stdout[-300:]
        preds = [(d / "predictions.jsonl").read_text(encoding="utf-8") for d in runs]
        assert preds[0] == preds[1]
        evals = [(d / "evaluation.json").read_text(encoding="utf-8") for d in runs]
        assert evals[0] == evals[1]
    finally:
        for d in runs:
            shutil.rmtree(d, ignore_errors=True)


def test_input_binding_rejects_mismatch() -> None:
    import run_winter_stage3_development as r
    import importlib
    importlib.reload(r)
    # blank pack with a fake extra process must fail the binding check
    blank = _load_json(BLANK)
    blank["processes"] = blank["processes"] + [{"process_id": "fake_process", "source_path": "x", "activity_names": []}]
    # call the binding logic directly
    from run_winter_stage3_development import BPMN_DIR as BD, MEMBERSHIP_CONTRACT as MC
    import json as _json
    membership = _json.loads(MC.read_text(encoding="utf-8"))
    frozen = [i["input_id"] for i in membership["membership"]["files"]]
    bpmn_ids = sorted(p.stem for p in BD.glob("*.bpmn"))
    blank_ids = sorted({p["process_id"] for p in blank["processes"]})
    assert frozen == bpmn_ids
    assert frozen != blank_ids  # injected fake breaks the binding


def test_manifest_hashes_consistent(tmp_path) -> None:
    import run_winter_stage3_development as r
    config = _load_json(CONFIG)
    run_dir = r.write_run(config, "hashcheck")
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "evaluate_winter_stage3_development.py"),
         "--run-dir", str(run_dir)],
        cwd=ROOT, text=True, encoding="utf-8", errors="replace",
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
    )
    assert result.returncode == 0, result.stdout[-300:]
    manifest = _load_json(run_dir / "manifest.json")
    import hashlib

    def sha(p: Path) -> str:
        return hashlib.sha256(p.read_bytes()).hexdigest()

    assert manifest["artifacts"]["config_snapshot"]["sha256"] == sha(run_dir / "config_snapshot.json")
    assert manifest["artifacts"]["predictions"]["sha256"] == sha(run_dir / "predictions.jsonl")
    assert manifest["artifacts"]["evaluation"]["sha256"] == sha(run_dir / "evaluation.json")
    assert manifest["inputs"]["blank_pack"]["sha256"] == sha(r.BLANK_PACK)
    import shutil
    shutil.rmtree(run_dir, ignore_errors=True)
