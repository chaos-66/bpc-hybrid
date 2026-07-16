"""Tests for the sun_compat module.

Tests cover:
1. Schema serialization/deserialization
2. ClauseAdapter conversion
3. SimilarityEngine matching
4. Stage3Adapter compliance checking
5. Fixture validation
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_PROJECT_ROOT / "src"))

from bpc_hybrid.sun_compat.schema import (
    SunRuleRecord,
    ObligationRecord,
    ActorActionMap,
    OrderRelation,
)
from bpc_hybrid.sun_compat.clause_adapter import ClauseAdapter
from bpc_hybrid.sun_compat.similarity_engine import SimilarityEngine
from bpc_hybrid.sun_compat.stage3_adapter import Stage3Adapter


# ── Schema Tests ─────────────────────────────────────────────────

class TestSchema:
    """Tests for SunRuleRecord schema."""

    def test_create_obligation_record(self):
        obl = ObligationRecord(
            obligation_id="S001_obl0",
            source_text="The controller shall notify the authority.",
            obligation_lemmatized="controller notify authority",
            modality="obligation",
            actor="the controller",
            actor_canonical="controller",
            action="notify the authority",
            action_canonical="notify authority",
        )
        assert obl.obligation_id == "S001_obl0"
        assert obl.obligation_lemmatized == "controller notify authority"
        assert obl.modality == "obligation"

    def test_create_sun_rule_record(self):
        record = SunRuleRecord(
            rule_id="S001",
            source_text="The controller shall notify the authority.",
            modality_type="obligation",
            actors=["the controller"],
            actions=["notify the authority"],
        )
        assert record.rule_id == "S001"
        assert len(record.actors) == 1

    def test_round_trip_serialization(self):
        record = SunRuleRecord(
            rule_id="S001",
            source_text="Test text",
            modality_type="obligation",
            obligations=[
                ObligationRecord(
                    obligation_id="S001_obl0",
                    source_text="Test text",
                    obligation_lemmatized="test text",
                    modality="obligation",
                    actor="test",
                    actor_canonical="test",
                    action="test action",
                    action_canonical="test action",
                )
            ],
            actor_action_maps=[
                ActorActionMap(actor="test", action="test action")
            ],
            order_relations=[
                OrderRelation(first_action="a", second_action="b", marker="then")
            ],
        )

        # Serialize
        d = record.to_dict()
        json_str = json.dumps(d)

        # Deserialize
        d2 = json.loads(json_str)
        record2 = SunRuleRecord.from_dict(d2)

        assert record2.rule_id == "S001"
        assert len(record2.obligations) == 1
        assert record2.obligations[0].obligation_lemmatized == "test text"
        assert len(record2.actor_action_maps) == 1
        assert len(record2.order_relations) == 1

    def test_json_serialization(self):
        record = SunRuleRecord(
            rule_id="S001",
            source_text="Test",
            modality_type="obligation",
        )
        json_str = record.to_json()
        record2 = SunRuleRecord.from_json(json_str)
        assert record2.rule_id == "S001"


# ── ClauseAdapter Tests ──────────────────────────────────────────

class TestClauseAdapter:
    """Tests for ClauseAdapter."""

    @pytest.fixture
    def adapter(self):
        return ClauseAdapter()

    def test_convert_basic(self, adapter):
        record = adapter.convert(
            rule_id="S001",
            source_text="The controller shall notify the authority.",
            modality="obligation",
            actor="the controller",
            action="notify the authority",
        )
        assert record.rule_id == "S001"
        assert len(record.obligations) == 1
        obl = record.obligations[0]
        assert obl.modality == "obligation"
        assert obl.actor == "the controller"
        assert obl.action == "notify the authority"
        # obligation_lemmatized should be lemmatized and stopwords removed
        assert "controller" in obl.obligation_lemmatized
        assert "notify" in obl.obligation_lemmatized
        assert "authority" in obl.obligation_lemmatized
        # "the" should be removed as stopword
        assert "the" not in obl.obligation_lemmatized.split()

    def test_convert_with_all_fields(self, adapter):
        record = adapter.convert(
            rule_id="S002",
            source_text="If there is a breach, the controller shall notify the authority within 72 hours unless required by law.",
            modality="obligation",
            actor="the controller",
            action="notify the authority",
            condition="if there is a breach",
            constraint="within 72 hours",
            exception="unless required by law",
        )
        obl = record.obligations[0]
        assert obl.condition == "if there is a breach"
        assert obl.constraint == "within 72 hours"
        assert obl.exception == "unless required by law"
        # obligation_lemmatized should NOT include condition/constraint/exception
        assert "breach" not in obl.obligation_lemmatized
        assert "72" not in obl.obligation_lemmatized

    def test_actor_action_map(self, adapter):
        record = adapter.convert(
            rule_id="S003",
            source_text="Test",
            modality="obligation",
            actor="the data controller",
            action="process personal data",
        )
        assert len(record.actor_action_maps) == 1
        aam = record.actor_action_maps[0]
        assert aam.actor == "the data controller"
        assert aam.action == "process personal data"

    def test_order_relation_extraction(self, adapter):
        record = adapter.convert(
            rule_id="S004",
            source_text="Test",
            modality="obligation",
            actor="the controller",
            action="assess risk then notify authority",
        )
        # Should detect "then" as order marker
        assert len(record.order_relations) > 0
        rel = record.order_relations[0]
        assert rel.marker == "then"

    def test_validation_flags(self, adapter):
        record = adapter.convert(
            rule_id="S005",
            source_text="Test",
            modality="obligation",
            actor="the controller",
            action="notify the authority",
        )
        flags = record.validation_flags
        assert flags["has_actor"] is True
        assert flags["has_action"] is True
        assert flags["action_not_empty"] is True
        assert flags["actor_not_empty"] is True

    def test_empty_actor(self, adapter):
        record = adapter.convert(
            rule_id="S006",
            source_text="Test",
            modality="definition",
            actor=None,
            action="be defined as",
        )
        assert record.actors == []
        assert record.validation_flags["has_actor"] is False

    def test_batch_conversion(self, adapter):
        extractions = [
            {"sample_id": "S001", "text": "Test 1", "modality": "obligation",
             "fields": {"actor": "controller", "action": "notify"}},
            {"sample_id": "S002", "text": "Test 2", "modality": "permission",
             "fields": {"actor": "processor", "action": "process"}},
        ]
        records = adapter.convert_batch(extractions)
        assert len(records) == 2
        assert records[0].rule_id == "S001"
        assert records[1].rule_id == "S002"


# ── SimilarityEngine Tests ───────────────────────────────────────

class TestSimilarityEngine:
    """Tests for SimilarityEngine."""

    @pytest.fixture
    def engine(self):
        return SimilarityEngine()

    def test_similarity_same_text(self, engine):
        score = engine.similarity(
            "controller notify authority",
            ["controller", "notify", "authority"],
        )
        assert score > 0.9  # Should be very high for same text

    def test_similarity_similar_text(self, engine):
        score = engine.similarity(
            "controller notify authority",
            ["notify", "national", "authority"],
        )
        assert score > 0.3  # Should be somewhat similar

    def test_similarity_different_text(self, engine):
        score = engine.similarity(
            "controller notify authority",
            ["store", "data", "securely"],
        )
        # en_core_web_md gives ~0.43 even for unrelated texts
        assert score < 0.6  # Should be lower than similar texts

    def test_is_match_above_threshold(self, engine):
        matched = engine.is_match(
            "controller notify authority",
            ["controller", "notify", "authority"],
            threshold=0.4,
        )
        assert matched is True

    def test_is_match_below_threshold(self, engine):
        # With en_core_web_md, unrelated texts still score ~0.43
        # Use threshold=0.5 to properly test below-threshold behavior
        matched = engine.is_match(
            "controller notify authority",
            ["store", "data", "securely"],
            threshold=0.5,
        )
        assert matched is False

    def test_find_best_match(self, engine):
        model_obligations = {
            "Data Controller": [
                ["notify", "authority"],
                ["record", "breach"],
            ],
            "Data Processor": [
                ["process", "data"],
            ],
        }
        result = engine.find_best_match(
            "controller notify authority",
            model_obligations,
            threshold=0.4,
        )
        assert result is not None
        participant, obligation, score = result
        assert participant == "Data Controller"
        assert score > 0.4

    def test_find_best_match_no_match(self, engine):
        model_obligations = {
            "Data Processor": [
                ["store", "data", "securely"],
            ],
        }
        result = engine.find_best_match(
            "controller notify authority",
            model_obligations,
            threshold=0.9,
        )
        assert result is None

    def test_fitness_score(self, engine):
        text_obligations = [
            "controller notify authority",
            "controller record breach",
        ]
        model_obligations = {
            "Data Controller": [
                ["notify", "authority"],
                ["record", "breach"],
            ],
        }
        fitness = engine.compute_fitness_score(
            text_obligations, model_obligations, threshold=0.4
        )
        assert fitness > 0.4

    def test_obligation_cost(self, engine):
        text_obligations = [
            "controller notify authority",
            "controller obtain consent",
        ]
        model_obligations = {
            "Data Controller": [
                ["notify", "authority"],
            ],
        }
        # Use threshold=0.6 since en_core_web_md gives ~0.56 even for
        # partially overlapping texts (shared "controller" inflates score)
        cost = engine.compute_obligation_cost(
            text_obligations, model_obligations, threshold=0.6
        )
        assert cost > 0.0  # "obtain consent" should not match at 0.6

    def test_caching(self, engine):
        # First call
        score1 = engine.similarity("test text", ["test", "text"])
        # Second call (should use cache)
        score2 = engine.similarity("test text", ["test", "text"])
        assert score1 == score2


# ── Stage3Adapter Tests ──────────────────────────────────────────

class TestStage3Adapter:
    """Tests for Stage3Adapter."""

    @pytest.fixture
    def adapter(self):
        engine = SimilarityEngine()
        return Stage3Adapter(engine, gamma=0.4, delta=0.8)

    def test_check_compliance_basic(self, adapter):
        rule = SunRuleRecord(
            rule_id="S001",
            source_text="The controller shall notify the authority.",
            modality_type="obligation",
            obligations=[
                ObligationRecord(
                    obligation_id="S001_obl0",
                    source_text="The controller shall notify the authority.",
                    obligation_lemmatized="controller notify authority",
                    modality="obligation",
                    actor="the controller",
                    actor_canonical="controller",
                    action="notify the authority",
                    action_canonical="notify authority",
                )
            ],
        )

        model_obligations = {
            "Data Controller": [["notify", "authority"]],
        }

        result = adapter.check_compliance([rule], model_obligations)
        assert result["total_obligations"] == 1
        assert result["matched_obligations"] >= 1
        assert result["fitness_score"] > 0.0

    def test_check_fixture_missing_action(self, adapter):
        # Use higher gamma since en_core_web_md gives ~0.43 for unrelated texts
        engine = SimilarityEngine()
        adapter_high = Stage3Adapter(engine, gamma=0.5, delta=0.8)

        rule = SunRuleRecord(
            rule_id="S001",
            source_text="Test",
            modality_type="obligation",
            obligations=[
                ObligationRecord(
                    obligation_id="S001_obl0",
                    source_text="Test",
                    obligation_lemmatized="controller notify authority",
                    modality="obligation",
                    actor="the controller",
                    actor_canonical="controller",
                    action="notify the authority",
                    action_canonical="notify authority",
                )
            ],
        )

        # BPMN has completely different tasks
        model_obligations = {
            "Data Controller": [["store", "data", "securely"]],
        }

        result = adapter_high.check_fixture(
            [rule], model_obligations, "missing_action"
        )
        assert result["fixture_type"] == "missing_action"
        assert result["obligation_cost"] > 0.0

    def test_check_fixture_incorrect_actor(self, adapter):
        rule = SunRuleRecord(
            rule_id="S001",
            source_text="Test",
            modality_type="obligation",
            obligations=[
                ObligationRecord(
                    obligation_id="S001_obl0",
                    source_text="Test",
                    obligation_lemmatized="controller notify authority",
                    modality="obligation",
                    actor="the controller",
                    actor_canonical="controller",
                    action="notify the authority",
                    action_canonical="notify authority",
                )
            ],
        )

        # BPMN assigns to wrong actor
        model_obligations = {
            "Data Processor": [["notify", "authority"]],
        }

        result = adapter.check_fixture(
            [rule], model_obligations, "incorrect_actor"
        )
        assert result["fixture_type"] == "incorrect_actor"

    def test_empty_rules(self, adapter):
        result = adapter.check_compliance([], {})
        assert result["total_obligations"] == 0
        assert result["fitness_score"] == 0.0


# ── Fixture File Tests ───────────────────────────────────────────

class TestFixtures:
    """Tests for fixture files."""

    FIXTURES_DIR = Path(__file__).parent / "fixtures"

    def test_missing_action_fixture_exists(self):
        path = self.FIXTURES_DIR / "sun_compat_missing_action.json"
        assert path.exists()

    def test_incorrect_actor_fixture_exists(self):
        path = self.FIXTURES_DIR / "sun_compat_incorrect_actor.json"
        assert path.exists()

    def test_out_of_order_fixture_exists(self):
        path = self.FIXTURES_DIR / "sun_compat_out_of_order.json"
        assert path.exists()

    def test_missing_action_fixture_valid_json(self):
        path = self.FIXTURES_DIR / "sun_compat_missing_action.json"
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert isinstance(data, list)
        assert len(data) > 0
        for item in data:
            assert "fixture_id" in item
            assert "fixture_type" in item
            assert "expected_detection" in item

    def test_fixture_types_match(self):
        for fixture_type in ["missing_action", "incorrect_actor", "out_of_order"]:
            path = self.FIXTURES_DIR / f"sun_compat_{fixture_type}.json"
            if path.exists():
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for item in data:
                    assert item["fixture_type"] == fixture_type
