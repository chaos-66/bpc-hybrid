"""Focused persistence and actual Tk interaction checks; only tmp_path is writable."""
import copy
import importlib.util
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from formal_experiment.stage3_binding_review import BindingReviewStore, SOURCE, BLANK, digest, read_json


@pytest.fixture
def store(tmp_path):
    return BindingReviewStore(output=tmp_path / "decisions.json")


def test_open_and_navigation_do_not_create_decisions(store):
    before = (digest(SOURCE), digest(BLANK))
    assert len(store.items) == 30 and store.resume_index() == 0
    assert store.document["records"] == {}
    assert store.next_pending(29) == 0
    assert not store.output.exists()
    assert (digest(SOURCE), digest(BLANK)) == before


def test_accept_resume_edit_backup_and_source_preservation(store):
    before = (digest(SOURCE), digest(BLANK))
    pair = store.items[0]["pair_id"]
    store.save(pair, "accept", store.current(pair), "人工测试备注")
    first = store.output.read_bytes()
    resumed = BindingReviewStore(output=store.output)
    assert resumed.resume_index() == 1
    assert resumed.document["records"][pair]["decision"] == "accepted"
    edited = resumed.current(pair)
    edited["action_id"] = None
    resumed.save(pair, "accept", edited, "选择留空")
    doc = read_json(store.output)
    assert doc["records"][pair]["decision"] == "edited"
    assert doc["records"][pair]["action_text"] is None
    assert doc["records"][pair]["note"] == "选择留空"
    assert first in [p.read_bytes() for p in (store.output.parent / "stage3_binding_review_backups").glob("*.json")]
    assert (digest(SOURCE), digest(BLANK)) == before


def test_all_thirty_finish_without_gold_and_resume(store):
    for i, row in enumerate(store.items):
        pair = row["pair_id"]
        store.save(pair, "reject" if i == 2 else "accept", store.current(pair))
        assert store.document["status"] == ("human_review_complete" if i == 29 else "in_progress")
    doc = read_json(store.output)
    assert doc["reviewed_count"] == 30
    assert doc["rejected_count"] == 1 and doc["is_gold"] is False
    assert doc["accepted_missing_actor_span_count"] == 8
    assert store.next_pending(29) is None
    resumed = BindingReviewStore(output=store.output)
    assert resumed.document == doc


@pytest.mark.parametrize("field,value", [
    ("action_id", "invented.action"),
    ("actor_id", "gdpr_article16_s001.c1.actor.1"),
    ("expected_lane_id", "another-lane"),
    ("order_scope", "rule_order"),
])
def test_invalid_edits_never_write(store, field, value):
    pair = store.items[0]["pair_id"]
    values = store.current(pair)
    values[field] = value
    with pytest.raises(ValueError):
        store.save(pair, "accept", values)
    assert not store.output.exists() and not store.document["records"]


def test_process_order_is_not_implicitly_a_rule_order(store):
    pair = "syn_out_of_order_02"  # both endpoints map to the same action
    values = store.current(pair)
    assert values["order_before_action_id"] == values["order_after_action_id"]
    store.save(pair, "accept", values)
    assert store.document["records"][pair]["values"]["order_scope"] == "process_only"
    before = store.output.read_bytes()
    values["order_scope"] = "rule_order"
    with pytest.raises(ValueError, match="两个不同"):
        store.save(pair, "accept", values)
    assert store.output.read_bytes() == before
    pair = "syn_out_of_order_01"
    values = store.current(pair)
    values["order_scope"] = "rule_order"
    store.save(pair, "accept", values, "明确确认两个动作的先后")
    assert store.document["records"][pair]["values"]["order_scope"] == "rule_order"


def test_null_candidate_is_an_explicit_completed_review(store):
    pair = "syn_incorrect_actor_03"
    assert store.current(pair)["action_id"] is None
    store.save(pair, "accept", store.current(pair))
    assert store.document["records"][pair]["review_state"] == "reviewed"
    assert store.document["accepted_missing_action_count"] == 1


def test_second_window_cannot_overwrite_newer_progress(store):
    other = BindingReviewStore(output=store.output)
    pair = store.items[0]["pair_id"]
    store.save(pair, "accept", store.current(pair))
    saved = store.output.read_bytes()
    with pytest.raises(ValueError, match="另一个窗口"):
        other.save(pair, "reject", other.current(pair))
    assert store.output.read_bytes() == saved
    assert other.document["records"] == {}


def test_replace_failure_preserves_previous_file(store, monkeypatch):
    pair = store.items[0]["pair_id"]
    store.save(pair, "accept", store.current(pair))
    before = store.output.read_bytes()
    def fail(*args):
        raise OSError("disk unavailable")
    monkeypatch.setattr("formal_experiment.stage3_binding_review.os.replace", fail)
    with pytest.raises(OSError):
        store.save(pair, "reject", store.current(pair))
    assert store.output.read_bytes() == before
    assert store.document["records"][pair]["choice"] == "accept"
    assert not list(store.output.parent.glob("*.tmp"))


def test_changed_source_and_mismatched_resume_are_refused(tmp_path):
    source = tmp_path / "source.json"
    source.write_bytes(SOURCE.read_bytes())
    store = BindingReviewStore(source=source, output=tmp_path / "decisions.json")
    pair = store.items[0]["pair_id"]
    store.save(pair, "accept", store.current(pair))
    before = store.output.read_bytes()
    source.write_bytes(source.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="来源已变化"):
        store.save(pair, "accept", store.current(pair))
    with pytest.raises(ValueError, match="不匹配"):
        BindingReviewStore(source=source, output=store.output)
    assert store.output.read_bytes() == before


def test_actual_tk_buttons_complete_and_reload_only_temp_decisions(store, monkeypatch):
    import tkinter as tk
    spec = importlib.util.spec_from_file_location("binding_review_gui", ROOT / "scripts/stage3_binding_review_tool.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tk display is unavailable")
    root.withdraw()
    def unexpected_error(*args, **kwargs):
        raise AssertionError(str(args))
    monkeypatch.setattr(module.messagebox, "showerror", unexpected_error)
    try:
        ui = module.ReviewWindow(root, store)
        root.update()
        assert ui.body.master is ui.canvas
        assert ui.canvas.winfo_parent() == str(ui.canvas.master)
        ui.move(1)
        assert not store.output.exists()
        ui.move(-1)
        # All proposed values are accepted in an isolated test output only.
        for _ in range(30):
            ui.accept_button.invoke()
            root.update()
        assert store.document["reviewed_count"] == 30
        assert "审核完成" in ui.status.cget("text")
        assert store.output.exists()
    finally:
        root.destroy()
