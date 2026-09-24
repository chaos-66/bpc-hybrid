# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

from bpc_hybrid.winter_stage3.global_roles import collect_global_role_candidates


def test_collect_global_roles_from_inference_view_only(tmp_path: Path) -> None:
    bpmn = tmp_path / "a.bpmn"
    bpmn.write_text(
        '<definitions xmlns="http://www.omg.org/spec/BPMN/20100524/MODEL">'
        '<process id="Process" name=" Controller " /></definitions>',
        encoding="utf-8",
    )
    view = {"items": [{"case_id": "case_a", "bpmn_path": "a.bpmn", "process_id": "Process"}]}
    result = collect_global_role_candidates(view, tmp_path)
    assert result["roles"] == ["controller"]
    assert result["role_count"] == 1
    assert list(result["model_sources"]) == ["a.bpmn"]
    assert "construction_reference.json" in result["forbidden_inputs"]
