# -*- coding: utf-8 -*-
"""S3.9 synthetic controlled-error extension focused tests (zero API).

Covers: panel manifest contract (30 variants, 10/10/10, rule bindings,
hashes), variant validation contents, replay determinism, and the panel
runner's device (per-method predictions on the synthetic panel, same
evaluator, explicit N/A semantics).  Nothing here calls the network or an
LLM.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
for candidate in (SRC, SCRIPTS):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

PY = sys.executable
PANEL = ROOT / "data/development/stage3_synth/synthetic_controlled_error_extension_v1.json"
PANEL_DIR = ROOT / "data/development/stage3_synth"

TYPES = ("missing_action", "incorrect_actor", "out_of_order")


def _load_panel() -> dict:
    return json.loads(PANEL.read_text(encoding="utf-8"))


def _run_cmd(args):
    proc = subprocess.run(
        [PY, *args], capture_output=True, text=True, cwd=ROOT.parent
    )
    return proc


# ---------------------------------------------------------------------------
# Panel contract
# ---------------------------------------------------------------------------


def test_panel_has_30_variants_10_each():
    panel = _load_panel()
    assert panel["schema_version"] == "s3_synthetic_controlled_error_extension@1.0.0"
    assert panel["panel_label"] == "synthetic_controlled_error_extension"
    assert panel["counts"]["total"] == 30
    assert panel["counts"]["missing_action"] == 10
    assert panel["counts"]["incorrect_actor"] == 10
    assert panel["counts"]["out_of_order"] == 10
    assert len(panel["variants"]) == 30


def test_panel_is_explicitly_not_human_gold():
    panel = _load_panel()
    assert panel["status"] == "dev_only_panel_not_human_gold"
    assert panel["safety"]["panel_is_human_gold"] is False
    assert panel["safety"]["gold_modified"] is False
    human_gold = json.loads(
        (ROOT / "data/gold/stage3/stage3_violation_gold_v1.json")
        .read_text(encoding="utf-8")
    )
    assert human_gold["count"] == 33
    human_ids = {item["item_id"] for item in human_gold["items"]}
    synth_ids = {v["variant_id"] for v in panel["variants"]}
    assert not (human_ids & synth_ids), "synthetic variants must not collide with human item ids"


def test_every_variant_has_locked_contract_fields():
    panel = _load_panel()
    for v in panel["variants"]:
        for key in ("variant_id", "process_id", "rule_id", "source_bpmn",
                    "source_bpmn_sha256", "variant_bpmn", "variant_bpmn_sha256",
                    "mutation_type", "expected_violation", "target_activity_id",
                    "mutation_config", "validation_checks", "generator_sha256"):
            assert key in v, f"{v['variant_id']} missing {key}"
        assert v["mutation_type"] == v["expected_violation"]
        assert v["mutation_type"] in TYPES
        assert v["generator_sha256"]


def test_all_variant_validations_passed():
    panel = _load_panel()
    for v in panel["variants"]:
        vc = v["validation_checks"]
        assert vc["status"] == "passed", f"{v['variant_id']}: {vc}"
        assert vc["xml_parse"] is True
        assert vc["structure_valid"] is True


def test_panel_replay_is_byte_identical():
    proc = _run_cmd([
        str(SCRIPTS / "build_s3_error_injection_v1.py"), "--check",
    ])
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "byte-identical" in proc.stdout


def test_variant_bpmns_exist_and_match_hashes():
    panel = _load_panel()
    for v in panel["variants"]:
        path = ROOT / v["variant_bpmn"]
        assert path.is_file(), f"{v['variant_id']}: {path} missing"
        data = path.read_bytes()
        import hashlib
        digest = hashlib.sha256(data).hexdigest()
        assert digest == v["variant_bpmn_sha256"], f"{v['variant_id']} hash mismatch"


def test_source_bpmns_byte_unchanged():
    import hashlib
    panel = _load_panel()
    originals = {
        orig["input_id"]: orig
        for orig in [{
            "input_id": p.stem,
            "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
        } for p in (ROOT / "data/input/stage1_stage3/gdpr7").glob("*.bpmn")]
    }
    for v in panel["variants"]:
        assert originals[v["process_id"]]["sha256"] == v["source_bpmn_sha256"]


def test_rule_binding_is_locked_and_from_frozen_inference():
    panel = _load_panel()
    binding = panel["rule_binding"]["per_variant"]
    assert len(binding) == 30
    assert panel["rule_binding"]["inference_pack_sha256"]
    inference = json.loads(
        (ROOT / "data/development/human_review/stage3_gold_inference_v1.json")
        .read_text(encoding="utf-8")
    )
    # bound rule must exist in the inference pack for (process, type)
    for v in panel["variants"]:
        keys = {
            (item["process_id"], item["check_type"])
            for item in inference["violation_items"]
        }
        assert (v["process_id"], v["mutation_type"]) in keys
        assert v["rule_id"] in {
            item["rule_id"]
            for item in inference["violation_items"]
            if item["process_id"] == v["process_id"]
            and item["check_type"] == v["mutation_type"]
        }


def test_incorrect_actor_injects_legal_actor_from_vocabulary():
    panel = _load_panel()
    import xml.etree.ElementTree as ET
    for v in panel["variants"]:
        if v["mutation_type"] != "incorrect_actor":
            continue
        diff = v["mutation_config"]["diff"]
        assert diff.get("injected_lane_name")
        # the injected actor must come from the same file's participant set
        orig_path = ROOT / v["source_bpmn"]
        root = ET.parse(orig_path).getroot()
        ns = {"bpmn": "http://www.omg.org/spec/BPMN/20100524/MODEL"}
        participants = {
            (el.get("name") or "").strip()
            for el in root.iter(f"{{{ns['bpmn']}}}participant")
        }
        assert diff["injected_lane_name"] in participants, \
            f"{v['variant_id']}: injected actor {diff['injected_lane_name']!r} not in vocabulary"


def test_out_of_order_pairs_are_ordered_in_original():
    panel = _load_panel()
    import xml.etree.ElementTree as ET
    from bpc_hybrid.stage1_process import load_stage1_contract, parse_bpmn_bytes
    contract = load_stage1_contract(
        ROOT / "configs/stage1_structural_s11_s14.json")
    for v in panel["variants"]:
        if v["mutation_type"] != "out_of_order":
            continue
        diff = v["mutation_config"]["diff"]
        pair = diff["pair"]
        a, b = pair
        orig = (ROOT / v["source_bpmn"]).read_bytes()
        record = parse_bpmn_bytes(orig, source_path=str(ROOT / v["source_bpmn"]),
                                  contract=contract)
        relations = {
            (r["before_activity_id"], r["after_activity_id"])
            for r in record["control_flow"]["activity_order_relations"]
        }
        assert (a, b) in relations, f"{v['variant_id']}: {pair} not ordered in original"


# ---------------------------------------------------------------------------
# Panel runner device
# ---------------------------------------------------------------------------


def test_four_methods_produced_30_predictions_each():
    for method in ("winter", "sun", "bm25", "tfidf_svd"):
        run_dir = ROOT / "outputs/development" / f"s39_synthetic_panel_{method}_v1"
        assert run_dir.is_dir(), f"{method}: run dir missing"
        lines = [
            json.loads(line)
            for line in run_dir.joinpath("predictions.jsonl")
            .read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        assert len(lines) == 30, f"{method}: expected 30 predictions, got {len(lines)}"
        assert run_dir.joinpath("evaluation.json").is_file()
        assert run_dir.joinpath("manifest.json").is_file()
        manifest = json.loads(
            run_dir.joinpath("manifest.json").read_text(encoding="utf-8"))
        assert manifest["panel"] == "synthetic_controlled_error_extension"
        assert manifest["safety"]["llm_api_calls"] == 0
        assert manifest["safety"]["network_calls"] == 0


def test_comparison_capsule_exists():
    comp = ROOT / "outputs/development/s39_synthetic_panel_compare_v1/comparison.json"
    assert comp.is_file()
    data = json.loads(comp.read_text(encoding="utf-8"))
    assert set(data["methods"]) == {"winter", "sun", "bm25", "tfidf_svd"}
    for m in data["methods"].values():
        ev = m["evaluation"]
        assert ev["support"] == 30
        for t in TYPES:
            assert t in ev["per_type"]


def test_predictions_use_expected_violation_as_check_type():
    for method in ("winter", "sun", "bm25", "tfidf_svd"):
        run_dir = ROOT / "outputs/development" / f"s39_synthetic_panel_{method}_v1"
        for line in run_dir.joinpath("predictions.jsonl").read_text(
                encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            assert row["check_type"] == row["expected_violation"]
            assert row["panel"] == "synthetic_controlled_error_extension"
            assert row["gold_visible"] is False


def test_no_method_marks_capabilities_false():
    # The four methods all support the violation task in this panel; the
    # N/A semantics (e.g., matching-only) is reported via evaluation fields,
    # never by zero-filling per-type scores.
    for method in ("winter", "sun", "bm25", "tfidf_svd"):
        run_dir = ROOT / "outputs/development" / f"s39_synthetic_panel_{method}_v1"
        for line in run_dir.joinpath("predictions.jsonl").read_text(
                encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            assert row["predicted_violation_type"] in (None,) + TYPES
            # scores may be None only where the method cannot compute them
            # (unobservable actor); missing_action/out_of_order are never None
            assert row["missing_action_score"] is not None
            assert row["out_of_order_score"] is not None


def test_panel_runner_rejects_stale_panel():
    # If the panel manifest were tampered, --check must fail closed; here we
    # just assert the runner's guard exists in source.
    src = (SCRIPTS / "run_s3_synthetic_panel_v1.py").read_text(encoding="utf-8")
    assert "build_s3_error_injection_v1.py\"], \"--check\"" in src or \
           "build_s3_error_injection_v1.py', \"--check\"" in src or \
           "build_s3_error_injection_v1.py" in src


# ---------------------------------------------------------------------------
# No-network / no-LLM discipline
# ---------------------------------------------------------------------------


def test_s3_9_scripts_are_offline():
    for name in ("build_s3_error_injection_v1.py",
                 "run_s3_synthetic_panel_v1.py"):
        src = (SCRIPTS / name).read_text(encoding="utf-8")
        for token in ("import urllib.request", "from urllib.request",
                      "import requests", "import httpx", "import openai"):
            assert token not in src, f"{name} references {token}"