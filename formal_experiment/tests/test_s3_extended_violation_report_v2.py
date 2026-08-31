# -*- coding: utf-8 -*-
"""S3.9-EXT paired control-plus-variant evaluation focused tests (zero API).

Covers the offline paired evaluation over the PERSISTED predictions
(no method re-runs): 40 controls + 40 variants per method; control Gold=none;
variant Gold=locked expected type; control predictions strictly re-derived
from persisted ``control_scores`` with the original thresholds and the fixed
EXTENDED_TYPES priority; failures/none/wrong-type/unobservable stay in every
denominator; control FP rate / paired accuracy / per-type P/R/F1 / 4-type and
5-class Macro-F1; the fixed 7-class overview (per-class F1 only, no joint
metrics); variant-only vs paired wording; byte-unchanged original artifacts;
deterministic report regeneration; zero API/network.
"""

from __future__ import annotations

import hashlib
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

from bpc_hybrid.stage3_extended_violations import (  # noqa: E402
    EXTENDED_TYPES,
    NONE_LABEL,
    control_prediction_from_scores,
    evaluate_paired,
)

PY = sys.executable
METHODS = ("winter", "sun", "bm25", "tfidf_svd")
PANEL = ROOT / "data/development/stage3_synth/synthetic_controlled_error_extension_v2.json"
REPORT_JSON = ROOT / "outputs/reports/s3_extended_violation_comparison_v2.json"
REPORT_MD = ROOT / "outputs/reports/s3_extended_violation_comparison_v2.md"
CONFIG = ROOT / "configs/stage3_extended_violation_v2.json"
GAMMA_EXT = 0.5

# byte-unchanged guards: original three-type artifacts + v2 panel + the four
# methods' ORIGINAL run artifacts (must never be touched by report-only mode)
V1_GOLD_SHA = "54245ef0d102ae5e7a44e8c45424ecd9e86e1e0d9ed43ac1a9cd43641c981550"
V1_PANEL_SHA = "e6b4da045a44ffc347a8de88909e005bef584335f63804d3c2155ef9242c3026"
V1_SCHEMA_SHA = "5b26d7f87be4a8cc29ef2cf80c7c2aacf1a752ecf192cdee3456ac50e36d280d"
V1_COMPARE_SHA = "a1409f65182399faae6da4eed38403200b01b7c24ca19444a9c1c70c8931b45a"
V2_PANEL_SHA = "6a23adbdbc0d8930ff2a33411c52fed7fbbf581fdd101f830c29b2e3373e2e81"
V2_RUN_SHA = {
    "winter": {
        "predictions.jsonl": "b37bc84ef7f289e2b0e029f51957003cc9dcd3ac96ef017507302df46e5351c2",
        "evaluation.json": "78a128710819af43c1682de0ebd3d45cac851cc1a016ec41c5bbf8ebc8226b75",
        "manifest.json": "ff2f1c008fffecf4f289bc6230032b3bb94a70fffb99072a2fde67ff5c89e1ab",
    },
    "sun": {
        "predictions.jsonl": "c5f2e1aab62d141d66d1d1b36bf7fe46703bece450253efc0e145ad515034979",
        "evaluation.json": "fc337534ce813c3d1a6c46ed1450c95d1d618a3523667789c4677f849b6e7c43",
        "manifest.json": "823b2d935184be9bb3fd0d9ea79f41f2b9819d485d0c71b77cbf401b5ee06105",
    },
    "bm25": {
        "predictions.jsonl": "f005c2613be4d3b89bd010c38c873a9b189d7aaa6259ec3225268df33f54730b",
        "evaluation.json": "59c87eb076a914145a64b222538acd9c2eb0b92c6d99c14cecede778b2ad31d8",
        "manifest.json": "61511f8bc50920e9d769743201f91c43d4afd6fe54d31770a27a130f0b4170eb",
    },
    "tfidf_svd": {
        "predictions.jsonl": "67f0e14986dbf8f6860fdbe3f83b7d15fa5071a416629d8dc7ee017da97498c1",
        "evaluation.json": "f4937000e05949b01f66172aaca9e2ed8c5b1d661134cd98c4f351755df1ee83",
        "manifest.json": "f88f952bca042dee9057bb237bfd604cf04538ec8ed414df2d9cb29908d400c5",
    },
}


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_panel() -> dict:
    return json.loads(PANEL.read_text(encoding="utf-8"))


def _predictions(method: str) -> list[dict]:
    return [
        json.loads(line)
        for line in (ROOT / "outputs/development"
                     / f"s3_extended_violation_panel_v2_{method}" / "predictions.jsonl")
        .read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _run_cmd(args) -> subprocess.CompletedProcess:
    return subprocess.run([PY, *args], capture_output=True, text=True, cwd=ROOT.parent)


# ---------------------------------------------------------------------------
# Control prediction rebuild: original thresholds + fixed priority
# ---------------------------------------------------------------------------


def _cs(score=None, observable=True, reason=None, contradiction=False):
    return {
        "score": score,
        "observable": observable,
        "reason": reason,
        "exact_contradiction": {"contradiction": contradiction},
    }


def test_control_prohibited_uses_gte_gamma_ext():
    scores = {t: _cs(score=0.0) for t in EXTENDED_TYPES}
    scores["prohibited_action_present"] = _cs(score=GAMMA_EXT)  # 0.5 -> violation
    assert control_prediction_from_scores(scores, GAMMA_EXT)["predicted"] == \
        "prohibited_action_present"
    scores["prohibited_action_present"] = _cs(score=GAMMA_EXT - 0.001)
    assert control_prediction_from_scores(scores, GAMMA_EXT)["predicted"] == NONE_LABEL


def test_control_condition_exception_use_gt_gamma_ext():
    for t in ("required_condition_not_enforced", "exception_not_handled"):
        scores = {x: _cs(score=0.0) for x in EXTENDED_TYPES}
        scores[t] = _cs(score=GAMMA_EXT)  # exactly 0.5 -> NOT a violation
        assert control_prediction_from_scores(scores, GAMMA_EXT)["predicted"] == NONE_LABEL
        scores[t] = _cs(score=GAMMA_EXT + 0.01)
        assert control_prediction_from_scores(scores, GAMMA_EXT)["predicted"] == t


def test_control_constraint_exact_contradiction_triggers_violation():
    scores = {x: _cs(score=0.0) for x in EXTENDED_TYPES}
    scores["constraint_violated"] = _cs(score=0.1, contradiction=True)
    assert control_prediction_from_scores(scores, GAMMA_EXT)["predicted"] == \
        "constraint_violated"


def test_control_priority_is_fixed_extension_types_order():
    # prohibited AND constraint both violate -> first in EXTENDED_TYPES wins
    scores = {x: _cs(score=0.0) for x in EXTENDED_TYPES}
    scores["prohibited_action_present"] = _cs(score=0.9)
    scores["constraint_violated"] = _cs(score=0.9)
    decision = control_prediction_from_scores(scores, GAMMA_EXT)
    assert decision["predicted"] == EXTENDED_TYPES[0] == "prohibited_action_present"


def test_control_all_unobservable_gives_none_prediction():
    scores = {t: _cs(observable=False, reason=f"empty_rule_{t}") for t in EXTENDED_TYPES}
    decision = control_prediction_from_scores(scores, GAMMA_EXT)
    assert decision["predicted"] is None
    assert decision["all_unobservable"] is True


def test_control_partial_unobservable_no_violation_is_none():
    scores = {x: _cs(score=0.0) for x in EXTENDED_TYPES}
    scores["required_condition_not_enforced"] = _cs(observable=False,
                                                    reason="empty_rule_condition")
    assert control_prediction_from_scores(scores, GAMMA_EXT)["predicted"] == NONE_LABEL


def test_control_prediction_uses_persisted_scores_only():
    # the rebuild must depend only on the control_scores dict fields
    scores = {x: _cs(score=0.0) for x in EXTENDED_TYPES}
    scores["exception_not_handled"] = _cs(score=0.8)
    assert control_prediction_from_scores(scores, GAMMA_EXT)["predicted"] == \
        "exception_not_handled"
    scores["exception_not_handled"] = _cs(score=0.2)
    assert control_prediction_from_scores(scores, GAMMA_EXT)["predicted"] == NONE_LABEL


# ---------------------------------------------------------------------------
# Paired evaluation on the REAL persisted predictions
# ---------------------------------------------------------------------------


def test_each_method_has_40_controls_and_40_variants():
    panel = _load_panel()
    assert len(panel["variants"]) == 40
    for method in METHODS:
        rows = _predictions(method)
        assert len(rows) == 40, method
        paired = evaluate_paired(rows, panel, GAMMA_EXT)
        assert paired["total_objects"] == 80
        assert paired["control_objects"] == 40
        assert paired["variant_objects"] == 40


def test_control_gold_all_none_and_variant_gold_matches_expected():
    panel = _load_panel()
    for method in METHODS:
        paired = evaluate_paired(_predictions(method), panel, GAMMA_EXT)
        assert paired["per_type"][NONE_LABEL]["support"] == 40
        assert sum(paired["per_type"][t]["support"] for t in EXTENDED_TYPES) == 40
        for v in panel["variants"]:
            assert v["expected_violation"] in EXTENDED_TYPES


def test_control_fp_rate_equals_per_type_fp_sum():
    panel = _load_panel()
    for method in METHODS:
        paired = evaluate_paired(_predictions(method), panel, GAMMA_EXT)
        fp_sum = sum(paired["per_type"][t]["fp"] for t in EXTENDED_TYPES)
        assert paired["control_false_positive_rate"] == round(fp_sum / 40, 4)
        assert 0.0 <= paired["control_false_positive_rate"] <= 1.0


def test_paired_accuracy_requires_control_none_and_variant_correct():
    panel = _load_panel()
    for method in METHODS:
        rows = _predictions(method)
        paired = evaluate_paired(rows, panel, GAMMA_EXT)
        manual = 0
        for v in panel["variants"]:
            row = next(r for r in rows if r["item_id"] == v["variant_id"])
            ctl = control_prediction_from_scores(row["control_scores"], GAMMA_EXT)["predicted"]
            var = row["predicted_violation_type"]
            if ctl == NONE_LABEL and var == v["expected_violation"]:
                manual += 1
        assert paired["paired_accuracy"] == round(manual / 40, 4)


def test_variant_exact_and_five_class_accuracy_manual():
    panel = _load_panel()
    for method in METHODS:
        rows = _predictions(method)
        paired = evaluate_paired(rows, panel, GAMMA_EXT)
        manual_variant = sum(
            1 for r in rows if r["predicted_violation_type"] == r["expected_violation"])
        assert paired["variant_exact_type_accuracy"] == round(manual_variant / 40, 4)
        manual_all = 0
        for v in panel["variants"]:
            row = next(r for r in rows if r["item_id"] == v["variant_id"])
            ctl = control_prediction_from_scores(row["control_scores"], GAMMA_EXT)["predicted"]
            manual_all += int(ctl == NONE_LABEL)
            manual_all += int(row["predicted_violation_type"] == v["expected_violation"])
        assert paired["five_class_accuracy"] == round(manual_all / 80, 4)


def test_per_type_prf1_manual_over_80_objects():
    panel = _load_panel()
    for method in METHODS:
        rows = _predictions(method)
        paired = evaluate_paired(rows, panel, GAMMA_EXT)
        items = []
        for v in panel["variants"]:
            row = next(r for r in rows if r["item_id"] == v["variant_id"])
            ctl = control_prediction_from_scores(row["control_scores"], GAMMA_EXT)["predicted"]
            items.append((NONE_LABEL, ctl))
            items.append((v["expected_violation"], row["predicted_violation_type"]))
        for label in (NONE_LABEL,) + EXTENDED_TYPES:
            tp = sum(1 for g, p in items if g == label and p == label)
            fp = sum(1 for g, p in items if p == label and g != label)
            fn = sum(1 for g, p in items if g == label and p != label)
            exp = paired["per_type"][label]
            assert exp["tp"] == tp and exp["fp"] == fp and exp["fn"] == fn
            assert exp["support"] == tp + fn
            precision = tp / (tp + fp) if (tp + fp) else 0.0
            recall = tp / (tp + fn) if (tp + fn) else 0.0
            f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
            assert exp["precision"] == round(precision, 4)
            assert exp["recall"] == round(recall, 4)
            assert exp["f1"] == round(f1, 4)


def test_macro_f1_four_and_five_are_separate():
    panel = _load_panel()
    for method in METHODS:
        paired = evaluate_paired(_predictions(method), panel, GAMMA_EXT)
        manual4 = sum(paired["per_type"][t]["f1"] for t in EXTENDED_TYPES) / 4
        manual5 = sum(paired["per_type"][l]["f1"]
                      for l in (NONE_LABEL,) + EXTENDED_TYPES) / 5
        assert paired["macro_f1_four_violation_types"] == round(manual4, 4)
        assert paired["macro_f1_five_classes"] == round(manual5, 4)
        assert paired["macro_f1_four_violation_types"] != paired["macro_f1_five_classes"]


def test_failures_none_and_unobservable_stay_in_denominators():
    panel = _load_panel()
    for method in METHODS:
        rows = _predictions(method)
        paired = evaluate_paired(rows, panel, GAMMA_EXT)
        # 80 objects; every object contributes to exactly one gold support
        assert sum(paired["per_type"][l]["support"] for l in
                   (NONE_LABEL,) + EXTENDED_TYPES) == 80
        # unobservable counts are additive and reasons are recorded
        unobs = paired["unobservable"]
        assert unobs["total"] == unobs["variant"] + unobs["control"]
        assert unobs["by_reason"]
        # wrong-type cannot occur with the frozen variant device, but the
        # field must exist and be an integer (controls add FP, not wrong-type)
        assert isinstance(paired["wrong_type"], int)


def test_paired_synthetic_small_sample_hand_computed():
    # 40 synthetic variants: first 20 detected (5 per type), last 20 missed
    # (10 of them unobservable via the observability flag)
    variants = []
    rows = []
    for i in range(40):
        expected = EXTENDED_TYPES[i % 4]
        vid = f"syn_test_{i:02d}"
        variants.append({"variant_id": vid, "process_id": "p", "rule_id": "r",
                         "expected_violation": expected})
        pred = expected if i < 20 else None
        # control scores: i<10 -> none; 10<=i<20 -> prohibited FP;
        # 20<=i<30 -> all unobservable; 30<=i<40 -> constraint FP
        if i < 10:
            cs = {t: _cs(score=0.0) for t in EXTENDED_TYPES}
        elif i < 20:
            cs = {t: _cs(score=0.0) for t in EXTENDED_TYPES}
            cs["prohibited_action_present"] = _cs(score=0.9)
        elif i < 30:
            cs = {t: _cs(observable=False, reason=f"empty_rule_{t}")
                  for t in EXTENDED_TYPES}
        else:
            cs = {t: _cs(score=0.0) for t in EXTENDED_TYPES}
            cs["constraint_violated"] = _cs(score=0.9)
        var_unobservable = 20 <= i < 30
        rows.append({
            "item_id": vid, "expected_violation": expected,
            "predicted_violation_type": pred,
            "control_scores": cs,
            "observability": {
                t: {"observable": not (var_unobservable and t == expected),
                    "reason": "synthetic_unobservable" if (var_unobservable and t == expected) else None}
                for t in EXTENDED_TYPES
            },
        })
    panel = {"variants": variants}
    paired = evaluate_paired(rows, panel, GAMMA_EXT)
    # hand-computed expectations
    assert paired["total_objects"] == 80
    assert paired["five_class_accuracy"] == round(30 / 80, 4)      # 10 ctl none + 20 var
    assert paired["variant_exact_type_accuracy"] == round(20 / 40, 4)
    assert paired["control_false_positive_rate"] == round(20 / 40, 4)
    assert paired["paired_accuracy"] == round(10 / 40, 4)           # i<10 pairs only
    assert paired["per_type"]["prohibited_action_present"]["tp"] == 5
    assert paired["per_type"]["prohibited_action_present"]["fp"] == 10
    assert paired["per_type"]["prohibited_action_present"]["fn"] == 5
    assert paired["per_type"][NONE_LABEL]["tp"] == 10
    assert paired["per_type"][NONE_LABEL]["fn"] == 30
    assert paired["unobservable"]["control"] == 10
    assert paired["unobservable"]["variant"] == 10
    assert paired["unobservable"]["total"] == 20


# ---------------------------------------------------------------------------
# Report structure: 7-class overview without joint metrics, wording, replay
# ---------------------------------------------------------------------------


def test_seven_class_overview_has_no_joint_metrics():
    data = json.loads(REPORT_JSON.read_text(encoding="utf-8"))
    overview = data["seven_class_overview"]
    assert set(overview) == {"note", "per_class_f1"}
    for method, f1s in overview["per_class_f1"].items():
        assert set(f1s) == {
            "missing_action", "incorrect_actor", "out_of_order",
        } | set(EXTENDED_TYPES)
    md = REPORT_MD.read_text(encoding="utf-8")
    seven_section = md.split("## 5.")[1].split("## 6.")[0]
    # the 7-class TABLE must not carry joint metric columns (the note may
    # mention that no joint Macro-F1 is computed)
    assert "| Macro-F1 |" not in seven_section
    assert "| Exact |" not in seven_section
    assert "| Unobservable |" not in seven_section
    assert "type coverage only" in seven_section
    assert "no joint Macro-F1" in seven_section


def test_report_distinguishes_variant_only_and_paired():
    md = REPORT_MD.read_text(encoding="utf-8")
    assert "variant-only detection evaluation" in md
    assert "paired control-plus-variant evaluation" in md
    data = json.loads(REPORT_JSON.read_text(encoding="utf-8"))
    assert data["schema_version"] == "s3_extended_violation_comparison@1.1.0"
    for m in data["methods"].values():
        assert m["variant_only_evaluation"]["support"] == 40
        assert m["paired_evaluation"]["total_objects"] == 80
        assert m["paired_evaluation"]["evaluation_kind"] == \
            "paired_control_plus_variant"


def test_conclusion_wording_is_tightened():
    md = REPORT_MD.read_text(encoding="utf-8")
    assert "FEASIBILITY" in md                       # prohibited
    assert "PARTIAL support" in md                   # constraint
    assert "OBSERVABILITY BOTTLENECK" in md          # condition
    assert "boundary events, exception branches" in md  # exception
    assert "NOT evidence that all four types 'prove downstream value'" in md
    data = json.loads(REPORT_JSON.read_text(encoding="utf-8"))
    analysis = data["analysis"]
    assert set(analysis["per_type_support_conclusion"]) == set(EXTENDED_TYPES)
    assert "explicit Stage 3 consumption interface" in \
        analysis["rule_record_downstream_value"]


def test_original_artifacts_byte_unchanged():
    assert _sha256_file(ROOT / "data/gold/stage3/stage3_violation_gold_v1.json") == V1_GOLD_SHA
    assert _sha256_file(
        ROOT / "data/development/stage3_synth/synthetic_controlled_error_extension_v1.json") == V1_PANEL_SHA
    assert _sha256_file(ROOT / "configs/schemas/stage3_prediction.schema.json") == V1_SCHEMA_SHA
    assert _sha256_file(
        ROOT / "outputs/development/s39_synthetic_panel_compare_v1/comparison.json") == V1_COMPARE_SHA
    assert _sha256_file(PANEL) == V2_PANEL_SHA
    # 40 v2 variants byte-unchanged via the locked manifest hashes
    panel = _load_panel()
    for v in panel["variants"]:
        for key, path in (("control_bpmn_sha256", v["control_bpmn"]),
                          ("variant_bpmn_sha256", v["variant_bpmn"])):
            assert _sha256_file(ROOT / path) == v[key], v["variant_id"]
    for method, files in V2_RUN_SHA.items():
        for name, digest in files.items():
            path = ROOT / "outputs/development" / f"s3_extended_violation_panel_v2_{method}" / name
            assert path.is_file(), path
            assert _sha256_file(path) == digest, f"{method}/{name} drifted"


def test_report_regeneration_is_deterministic():
    before_json = _sha256_file(REPORT_JSON)
    before_md = _sha256_file(REPORT_MD)
    proc = _run_cmd([
        str(SCRIPTS / "run_s3_extended_violation_panel_v2.py"), "--report-only",
    ])
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert _sha256_file(REPORT_JSON) == before_json
    assert _sha256_file(REPORT_MD) == before_md


def test_report_files_are_offline():
    for path in (
        SCRIPTS / "run_s3_extended_violation_panel_v2.py",
        SRC / "bpc_hybrid/stage3_extended_violations.py",
    ):
        src = path.read_text(encoding="utf-8")
        for token in ("import urllib.request", "from urllib.request",
                      "import requests", "import httpx", "import openai",
                      "import anthropic"):
            assert token not in src, f"{path.name} references {token}"
