# -*- coding: utf-8 -*-
"""Tests for the Stage 2 → Stage 3 compatibility audit script.

These tests verify that the audit script:
1. Correctly identifies bad JSON lines
2. Correctly converts valid predictions to Sun-compatible records
3. Issues appropriate warnings for action_too_long, missing_actor_action_map, etc.
4. Generates order_relations from then/before/after patterns
5. Works offline (no LLM, no .env, no network)
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_PROJECT_ROOT / "src"))
sys.path.insert(0, str(_PROJECT_ROOT / "scripts"))

from bpc_hybrid.sun_compat.clause_adapter import ClauseAdapter
from bpc_hybrid.sun_compat.schema import SunRuleRecord


@pytest.fixture(scope="module")
def adapter():
    """Shared ClauseAdapter for all tests."""
    return ClauseAdapter()


@pytest.fixture
def tmp_jsonl(tmp_path):
    """Helper to write a JSONL file and return its path."""
    def _write(lines: list[dict]) -> Path:
        p = tmp_path / "test.jsonl"
        with open(p, "w", encoding="utf-8") as f:
            for line in lines:
                f.write(json.dumps(line, ensure_ascii=False) + "\n")
        return p
    return _write


class TestAuditBadJson:
    """Audit script must identify and report bad JSON lines."""

    def test_bad_json_line_detected(self, adapter, tmp_path):
        from audit_stage2_to_stage3 import audit_file

        p = tmp_path / "bad.jsonl"
        with open(p, "w", encoding="utf-8") as f:
            f.write('{"sample_id": "good", "method": "test", "prediction_fields": {"modality": {"value": "obligation"}, "actor": {"value": "X"}, "action": {"value": "Y"}, "condition": {"value": ""}, "constraint": {"value": ""}, "exception": {"value": ""}}}\n')
            f.write('{"sam{"sample_id": "bad"}\n')  # corrupted
            f.write('{"sample_id": "good2", "method": "test", "prediction_fields": {"modality": {"value": "obligation"}, "actor": {"value": "A"}, "action": {"value": "B"}, "condition": {"value": ""}, "constraint": {"value": ""}, "exception": {"value": ""}}}\n')

        result = audit_file(adapter, p)
        assert result["total_lines"] == 3
        assert result["valid_json_lines"] == 2
        assert result["invalid_json_lines"] == 1
        assert len(result["bad_lines"]) == 1
        assert result["bad_lines"][0]["line_number"] == 2

    def test_empty_file(self, adapter, tmp_path):
        from audit_stage2_to_stage3 import audit_file

        p = tmp_path / "empty.jsonl"
        p.write_text("")
        result = audit_file(adapter, p)
        assert result["total_lines"] == 0

    def test_all_valid(self, adapter, tmp_jsonl):
        from audit_stage2_to_stage3 import audit_file

        good = {
            "sample_id": "t1", "method": "test",
            "prediction_fields": {
                "modality": {"value": "obligation"},
                "actor": {"value": "the controller"},
                "action": {"value": "notify the authority"},
                "condition": {"value": ""},
                "constraint": {"value": ""},
                "exception": {"value": ""},
            },
        }
        p = tmp_jsonl([good, good])
        result = audit_file(adapter, p)
        assert result["valid_json_lines"] == 2
        assert result["invalid_json_lines"] == 0


class TestAuditConversion:
    """Audit script must convert valid predictions to Sun-compatible records."""

    def test_convertible_prediction(self, adapter, tmp_jsonl):
        from audit_stage2_to_stage3 import audit_file

        pred = {
            "sample_id": "conv1", "method": "rule",
            "prediction_fields": {
                "modality": {"value": "obligation"},
                "actor": {"value": "the controller"},
                "action": {"value": "notify the supervisory authority"},
                "condition": {"value": "if there is a breach"},
                "constraint": {"value": "within 72 hours"},
                "exception": {"value": ""},
            },
        }
        p = tmp_jsonl([pred])
        result = audit_file(adapter, p)
        assert result["convertible_lines"] == 1
        rec = result["records"][0]
        assert rec["convertible"]
        assert rec["structural_flags"]["has_obligations"]
        assert rec["structural_flags"]["has_obligation_lemmatized"]
        assert rec["structural_flags"]["has_actor_action_map"]

    def test_missing_action_gives_error(self, adapter, tmp_jsonl):
        from audit_stage2_to_stage3 import audit_file

        pred = {
            "sample_id": "no_action", "method": "rule",
            "prediction_fields": {
                "modality": {"value": "obligation"},
                "actor": {"value": "the controller"},
                "action": {"value": ""},
                "condition": {"value": ""},
                "constraint": {"value": ""},
                "exception": {"value": ""},
            },
        }
        p = tmp_jsonl([pred])
        result = audit_file(adapter, p)
        rec = result["records"][0]
        assert any(e["type"] == "missing_action" for e in rec["errors"])


class TestAuditWarnings:
    """Audit script must issue appropriate warnings."""

    def test_action_too_long_warning(self, adapter, tmp_jsonl):
        from audit_stage2_to_stage3 import audit_file

        long_action = "notify " * 50  # 350 chars
        pred = {
            "sample_id": "long_act", "method": "rule",
            "prediction_fields": {
                "modality": {"value": "obligation"},
                "actor": {"value": "X"},
                "action": {"value": long_action},
                "condition": {"value": ""},
                "constraint": {"value": ""},
                "exception": {"value": ""},
            },
        }
        p = tmp_jsonl([pred])
        result = audit_file(adapter, p)
        rec = result["records"][0]
        assert any(w["type"] == "action_too_long" for w in rec["warnings"])

    def test_missing_actor_warning(self, adapter, tmp_jsonl):
        from audit_stage2_to_stage3 import audit_file

        pred = {
            "sample_id": "no_actor", "method": "rule",
            "prediction_fields": {
                "modality": {"value": "obligation"},
                "actor": {"value": ""},
                "action": {"value": "do something"},
                "condition": {"value": ""},
                "constraint": {"value": ""},
                "exception": {"value": ""},
            },
        }
        p = tmp_jsonl([pred])
        result = audit_file(adapter, p)
        rec = result["records"][0]
        assert any(w["type"] == "missing_actor" for w in rec["warnings"])
        assert any(w["type"] == "no_actor_action_map" for w in rec["warnings"])

    def test_action_contains_condition_marker(self, adapter, tmp_jsonl):
        from audit_stage2_to_stage3 import audit_file

        pred = {
            "sample_id": "leak", "method": "rule",
            "prediction_fields": {
                "modality": {"value": "obligation"},
                "actor": {"value": "X"},
                "action": {"value": "notify if there is a breach"},
                "condition": {"value": ""},
                "constraint": {"value": ""},
                "exception": {"value": ""},
            },
        }
        p = tmp_jsonl([pred])
        result = audit_file(adapter, p)
        rec = result["records"][0]
        assert any(w["type"] == "action_contains_condition_marker" for w in rec["warnings"])


class TestAuditOrderRelations:
    """Audit script must detect order relations from then/before/after."""

    def test_order_relations_from_then(self, adapter, tmp_jsonl):
        from audit_stage2_to_stage3 import audit_file

        pred = {
            "sample_id": "order1", "method": "rule",
            "prediction_fields": {
                "modality": {"value": "obligation"},
                "actor": {"value": "the controller"},
                "action": {"value": "assess the risk then notify the authority"},
                "condition": {"value": ""},
                "constraint": {"value": ""},
                "exception": {"value": ""},
            },
        }
        p = tmp_jsonl([pred])
        result = audit_file(adapter, p)
        rec = result["records"][0]
        assert rec["structural_flags"]["has_order_relations"]
        assert rec["structural_flags"]["order_relation_count"] >= 1

    def test_no_order_relations_when_absent(self, adapter, tmp_jsonl):
        from audit_stage2_to_stage3 import audit_file

        pred = {
            "sample_id": "no_order", "method": "rule",
            "prediction_fields": {
                "modality": {"value": "obligation"},
                "actor": {"value": "the controller"},
                "action": {"value": "notify the authority"},
                "condition": {"value": ""},
                "constraint": {"value": ""},
                "exception": {"value": ""},
            },
        }
        p = tmp_jsonl([pred])
        result = audit_file(adapter, p)
        rec = result["records"][0]
        assert not rec["structural_flags"]["has_order_relations"]


class TestAuditOffline:
    """Audit script must work completely offline."""

    def test_no_network_imports(self):
        """Verify audit script doesn't import network-related modules."""
        import importlib
        spec = importlib.util.find_spec("audit_stage2_to_stage3")
        assert spec is not None
        # Read the source and check for network imports
        with open(spec.origin, encoding="utf-8") as f:
            source = f.read()
        # Should not import requests, urllib, httpx, openai, etc.
        for forbidden in ["import requests", "import urllib", "import httpx", "import openai", "from openai"]:
            assert forbidden not in source, f"Audit script imports network module: {forbidden}"

    def test_no_dotenv_loading(self):
        """Verify audit script doesn't load .env or call LLM APIs."""
        import importlib
        spec = importlib.util.find_spec("audit_stage2_to_stage3")
        with open(spec.origin, encoding="utf-8") as f:
            source = f.read()
        for forbidden in ["load_dotenv", "dotenv", "LLMClient", "RealAPITransport"]:
            assert forbidden not in source, f"Audit script uses: {forbidden}"


class TestAuditRealFile:
    """Test audit against the actual r15_0 predictions file."""

    def test_r15_0_audit(self, adapter):
        from audit_stage2_to_stage3 import audit_file

        p = _PROJECT_ROOT / "_retired" / "data" / "legacy_r15_0" / "sun_rule_only_predictions.jsonl"
        if not p.exists():
            pytest.skip("r15_0 predictions file not found")

        result = audit_file(adapter, p)
        assert result["total_lines"] == 24
        assert result["invalid_json_lines"] == 0
        assert result["convertible_lines"] == 24
        # All 24 should be convertible
        assert result["summary"]["conversion_rate"] == 100.0


# ---------------------------------------------------------------------------
# B0-R1-A-C3 (2026-08-03) — manifest artifact integrity gate.
#
# These tests exercise the new ``verify_manifest_artifact_integrity``
# helper and confirm that the audit project registers the C3 manifest
# in the current checkout.
# ---------------------------------------------------------------------------

import hashlib
import json

from formal_experiment.audit import (
    _PASS_CODE as _C3_PASS_CODE,
    _FAIL_CODE as _C3_FAIL_CODE,
    verify_manifest_artifact_integrity,
)


def _write_artifact(path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content.encode("utf-8"))


def _sha256_bytes(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


class TestManifestArtifactIntegrity:
    """Manifest artifact integrity gate (B0-R1-A-C3)."""

    def test_valid_temp_manifest_passes(self, tmp_path):
        art1 = tmp_path / "art1.json"
        _write_artifact(art1, '{"x": 1}\n')
        art2 = tmp_path / "art2.json"
        _write_artifact(art2, '{"y": 2}\n')
        manifest = tmp_path / "manifest.json"
        manifest_payload = {
            "artifacts": {
                "a": {"path": "art1.json", "sha256": _sha256_bytes('{"x": 1}\n')},
                "b": {"path": "art2.json", "sha256": _sha256_bytes('{"y": 2}\n')},
            }
        }
        manifest.write_bytes(json.dumps(manifest_payload).encode("utf-8"))
        errs = verify_manifest_artifact_integrity(manifest)
        assert errs == []

    def test_missing_artifact(self, tmp_path):
        manifest = tmp_path / "manifest.json"
        manifest.write_bytes(
            json.dumps(
                {
                    "artifacts": {
                        "ghost": {
                            "path": "ghost.json",
                            "sha256": "0" * 64,
                        }
                    }
                }
            ).encode("utf-8")
        )
        errs = verify_manifest_artifact_integrity(manifest)
        assert len(errs) == 1
        assert errs[0].code == _C3_FAIL_CODE
        assert "missing" in errs[0].message.lower()

    def test_hash_mismatch(self, tmp_path):
        art = tmp_path / "art.json"
        _write_artifact(art, '{"z": 1}\n')
        manifest = tmp_path / "manifest.json"
        manifest.write_bytes(
            json.dumps(
                {
                    "artifacts": {
                        "a": {"path": "art.json", "sha256": "0" * 64},
                    }
                }
            ).encode("utf-8")
        )
        errs = verify_manifest_artifact_integrity(manifest)
        assert len(errs) == 1
        assert errs[0].code == _C3_FAIL_CODE
        assert "mismatch" in errs[0].message.lower()

    def test_illegal_sha256(self, tmp_path):
        art = tmp_path / "art.json"
        _write_artifact(art, "abc")
        manifest = tmp_path / "manifest.json"
        manifest.write_bytes(
            json.dumps(
                {
                    "artifacts": {
                        "a": {"path": "art.json", "sha256": "not-hex"},
                    }
                }
            ).encode("utf-8")
        )
        errs = verify_manifest_artifact_integrity(manifest)
        assert len(errs) == 1
        assert errs[0].code == _C3_FAIL_CODE
        assert "sha256" in errs[0].message.lower()

    def test_absolute_path_rejected(self, tmp_path):
        manifest = tmp_path / "manifest.json"
        manifest.write_bytes(
            json.dumps(
                {
                    "artifacts": {
                        "a": {
                            "path": str(tmp_path / "art.json"),
                            "sha256": "0" * 64,
                        }
                    }
                }
            ).encode("utf-8")
        )
        errs = verify_manifest_artifact_integrity(manifest)
        assert len(errs) == 1
        assert errs[0].code == _C3_FAIL_CODE
        assert "relative" in errs[0].message.lower()

    def test_parent_traversal_rejected(self, tmp_path):
        # Build a manifest that points at "../escape.json" which resolves
        # outside the manifest's parent directory.
        manifest = tmp_path / "manifest.json"
        manifest.write_bytes(
            json.dumps(
                {
                    "artifacts": {
                        "a": {
                            "path": "../escape.json",
                            "sha256": "0" * 64,
                        }
                    }
                }
            ).encode("utf-8")
        )
        errs = verify_manifest_artifact_integrity(manifest)
        assert len(errs) == 1
        assert errs[0].code == _C3_FAIL_CODE
        # Either "outside" (path-traversal wording) or "missing" (the
        # resolved file does not exist) is acceptable, but the entry
        # must NOT silently pass.
        assert errs[0].message != ""

    def test_non_json_or_non_object_manifest(self, tmp_path):
        # Non-JSON
        bad1 = tmp_path / "bad1.json"
        bad1.write_bytes(b"{not json")
        errs = verify_manifest_artifact_integrity(bad1)
        assert len(errs) == 1
        assert errs[0].code == _C3_FAIL_CODE
        # Non-object top level
        bad2 = tmp_path / "bad2.json"
        bad2.write_bytes(b"[]")
        errs = verify_manifest_artifact_integrity(bad2)
        assert len(errs) == 1
        assert errs[0].code == _C3_FAIL_CODE
        assert "object" in errs[0].message.lower()

    def test_registered_c3_manifest_passes_in_current_checkout(self):
        from formal_experiment.audit import collect_project_audit

        audit = collect_project_audit()
        pass_codes = {p["code"] for p in audit["findings"]["passes"]}
        assert _C3_PASS_CODE in pass_codes
        fail_codes = {e["code"] for e in audit["findings"]["errors"]}
        assert _C3_FAIL_CODE not in fail_codes
