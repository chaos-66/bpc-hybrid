"""Focused tests for approved shared role-surface normalization (zero API)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for candidate in (ROOT / "src",):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from bpc_hybrid.role_surface import normalize_role_surface, role_surfaces_equal  # noqa: E402
from bpc_hybrid.sun_stage3.sun_scorer import SunScorer  # noqa: E402


class _ZeroSim:
    def text_pair(self, left: str, right: str) -> float:
        return 0.0


class _RoleModel:
    def __init__(self, actors):
        self.actors = actors
        self.business_objects = []
        self.actor_sources = {actor: "actor" for actor in actors}


def test_casefold_whitespace_and_leading_article_only():
    assert normalize_role_surface("The Controller") == "controller"
    assert normalize_role_surface("a controller") == "controller"
    assert normalize_role_surface("an controller") == "controller"
    assert normalize_role_surface("the data controller") == "data controller"
    assert role_surfaces_equal("Controller", "the controller")


def test_controller_processor_remain_distinct():
    assert not role_surfaces_equal("controller", "processor")


def test_sun_scorer_uses_shared_normalization_without_synonyms():
    scorer = SunScorer(_ZeroSim(), tau=0.5, gamma=0.8, theta=0.8, nlp=None)
    assert scorer._best_actor_match("The Controller", _RoleModel(["Controller"])) == ("Controller", 1.0, "actor")
    assert scorer._best_actor_match("Controller", _RoleModel(["Processor"]))[0] is None
