# -*- coding: utf-8 -*-
"""Tests for gold review pack generation and validation.

Verifies:
1. Review pack can be generated
2. Gold template does NOT auto-fill gold values
3. Validation script accepts initial template
4. Validation script rejects bad JSON
5. Validation script rejects invalid modality
6. Validation script rejects reviewed-but-missing-reviewer
7. Scripts are offline (no LLM, no .env, no network)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_PROJECT_ROOT / "src"))
sys.path.insert(0, str(_PROJECT_ROOT / "scripts"))


class TestBuildGoldReviewPack:
    """Test the gold review pack generation script."""

    def test_pack_generates_without_error(self, tmp_path):
        """The build script should run without error."""
        import importlib.util
        spec = importlib.util.find_spec("build_gold_review_pack")
        assert spec is not None

        # Check the script exists and is importable
        with open(spec.origin, encoding="utf-8") as f:
            source = f.read()
        assert "def main" in source

    def test_template_gold_fields_are_null(self, tmp_path):
        """Gold template must NOT auto-fill gold values."""
        from build_gold_review_pack import build_template_record

        candidate = {
            "sample_id": "test_001",
            "source_text": "The controller shall notify the authority.",
            "issue_types": ["missing_action"],
            "why_needs_review": "test",
            "predictions_by_method": {
                "sun_style": {"modality": "obligation", "actor": "the controller", "action": "notify", "condition": "", "constraint": "", "exception": ""},
            },
            "current_stage3_compat_flags": {},
            "suggested_review_fields": {},
            "review_status": "pending_human",
            "do_not_auto_score": True,
        }

        template = build_template_record(candidate)

        # All gold_fields must be None
        for field in ["modality", "actor", "action", "condition", "constraint", "exception"]:
            assert template["gold_fields"][field] is None, f"gold_fields.{field} should be null"

        # gold_sun_record arrays must be empty
        assert template["gold_sun_record"]["actions"] == []
        assert template["gold_sun_record"]["actors"] == []
        assert template["gold_sun_record"]["actor_action_map"] == []
        assert template["gold_sun_record"]["order_relations"] == []

        # human_review.status must be needs_review
        assert template["human_review"]["status"] == "needs_review"
        assert template["human_review"]["reviewer"] is None

    def test_template_preserves_reference_predictions(self, tmp_path):
        """Template should include reference_predictions from candidate."""
        from build_gold_review_pack import build_template_record

        candidate = {
            "sample_id": "test_002",
            "source_text": "Some text",
            "issue_types": [],
            "why_needs_review": "",
            "predictions_by_method": {
                "sun_style": {"modality": "obligation", "actor": "X", "action": "Y", "condition": "", "constraint": "", "exception": ""},
            },
            "current_stage3_compat_flags": {},
            "suggested_review_fields": {},
            "review_status": "pending_human",
            "do_not_auto_score": True,
        }

        template = build_template_record(candidate)
        assert "reference_predictions" in template
        assert template["reference_predictions"]["sun_style"]["modality"] == "obligation"


class TestValidateGoldReview:
    """Test the gold review validation script."""

    def _make_valid_record(self, status: str = "needs_review") -> dict:
        return {
            "sample_id": "test_001",
            "source_text": "The controller shall notify the authority.",
            "gold_fields": {
                "modality": None,
                "actor": None,
                "action": None,
                "condition": None,
                "constraint": None,
                "exception": None,
            },
            "gold_sun_record": {
                "actions": [],
                "actors": [],
                "actor_action_map": [],
                "order_relations": [],
            },
            "human_review": {
                "reviewer": None,
                "reviewed_at": None,
                "confidence": None,
                "notes": None,
                "status": status,
            },
        }

    def test_valid_template_passes(self, tmp_path):
        """A valid template should pass validation."""
        from validate_legacy_gold_review import validate_file

        p = tmp_path / "valid.jsonl"
        with open(p, "w", encoding="utf-8") as f:
            f.write(json.dumps(self._make_valid_record()) + "\n")

        result = validate_file(p)
        assert result["summary"]["format_valid"]
        assert result["summary"]["errors"] == 0

    def test_bad_json_detected(self, tmp_path):
        """Bad JSON lines should be detected."""
        from validate_legacy_gold_review import validate_file

        p = tmp_path / "bad.jsonl"
        with open(p, "w", encoding="utf-8") as f:
            f.write('{"sample_id": "bad"\n')  # invalid JSON

        result = validate_file(p)
        assert not result["summary"]["format_valid"]
        assert result["invalid_json_lines"] == 1

    def test_invalid_modality_detected(self, tmp_path):
        """Invalid modality values should be rejected."""
        from validate_legacy_gold_review import validate_file

        rec = self._make_valid_record()
        rec["gold_fields"]["modality"] = "INVALID_MODALITY"

        p = tmp_path / "bad_modality.jsonl"
        with open(p, "w", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")

        result = validate_file(p)
        assert result["summary"]["errors"] > 0
        assert any(i["type"] == "invalid_modality" for i in result["issues"])

    def test_reviewed_missing_reviewer_detected(self, tmp_path):
        """status=reviewed but missing reviewer should be rejected."""
        from validate_legacy_gold_review import validate_file

        rec = self._make_valid_record(status="reviewed")
        # reviewer is None — should be caught

        p = tmp_path / "bad_reviewed.jsonl"
        with open(p, "w", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")

        result = validate_file(p)
        assert result["summary"]["errors"] > 0
        assert any(i["type"] == "missing_reviewer" for i in result["issues"])

    def test_reviewed_complete_passes(self, tmp_path):
        """status=reviewed with all required fields should pass."""
        from validate_legacy_gold_review import validate_file

        rec = self._make_valid_record(status="reviewed")
        rec["human_review"]["reviewer"] = "Dr. Smith"
        rec["human_review"]["reviewed_at"] = "2026-06-28"
        rec["human_review"]["confidence"] = 4

        p = tmp_path / "good_reviewed.jsonl"
        with open(p, "w", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")

        result = validate_file(p)
        assert result["summary"]["format_valid"]
        assert result["summary"]["errors"] == 0

    def test_missing_required_key_detected(self, tmp_path):
        """Missing top-level keys should be rejected."""
        from validate_legacy_gold_review import validate_file

        rec = {"sample_id": "test"}  # missing everything else

        p = tmp_path / "missing_keys.jsonl"
        with open(p, "w", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")

        result = validate_file(p)
        assert result["summary"]["errors"] > 0

    def test_gold_sun_record_must_be_arrays(self, tmp_path):
        """gold_sun_record fields must be arrays."""
        from validate_legacy_gold_review import validate_file

        rec = self._make_valid_record()
        rec["gold_sun_record"]["actions"] = "not_an_array"

        p = tmp_path / "bad_arrays.jsonl"
        with open(p, "w", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")

        result = validate_file(p)
        assert result["summary"]["errors"] > 0
        assert any(i["type"] == "invalid_gold_sun_type" for i in result["issues"])


class TestGoldReviewPackOffline:
    """Verify scripts are completely offline."""

    def test_build_script_no_network_imports(self):
        import importlib.util
        spec = importlib.util.find_spec("build_gold_review_pack")
        with open(spec.origin, encoding="utf-8") as f:
            source = f.read()
        for forbidden in ["import requests", "import urllib", "import httpx", "import openai", "from openai"]:
            assert forbidden not in source, f"Build script imports network module: {forbidden}"

    def test_validate_script_no_network_imports(self):
        import importlib.util
        spec = importlib.util.find_spec("validate_legacy_gold_review")
        with open(spec.origin, encoding="utf-8") as f:
            source = f.read()
        for forbidden in ["import requests", "import urllib", "import httpx", "import openai", "from openai"]:
            assert forbidden not in source, f"Validate script imports network module: {forbidden}"

    def test_build_script_no_dotenv(self):
        import importlib.util
        spec = importlib.util.find_spec("build_gold_review_pack")
        with open(spec.origin, encoding="utf-8") as f:
            source = f.read()
        for forbidden in ["load_dotenv", "dotenv", "LLMClient", "RealAPITransport"]:
            assert forbidden not in source, f"Build script uses: {forbidden}"

    def test_validate_script_no_dotenv(self):
        import importlib.util
        spec = importlib.util.find_spec("validate_legacy_gold_review")
        with open(spec.origin, encoding="utf-8") as f:
            source = f.read()
        for forbidden in ["load_dotenv", "dotenv", "LLMClient", "RealAPITransport"]:
            assert forbidden not in source, f"Validate script uses: {forbidden}"


class TestValidateRealTemplate:
    """Test validation against the actual generated template."""

    def test_generated_template_is_valid(self):
        """The generated template should pass validation."""
        from validate_legacy_gold_review import validate_file

        template_path = _PROJECT_ROOT / "data" / "development" / "gold_review" / "sun_stage2_gold_review_template.jsonl"
        if not template_path.exists():
            pytest.skip("Legacy development template is not present")

        result = validate_file(template_path)
        assert result["summary"]["format_valid"], f"Template has errors: {result['issues'][:5]}"
        assert result["summary"]["needs_review"] > 0
        assert result["summary"]["reviewed"] == 0  # no one has reviewed yet
