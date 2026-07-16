"""Sun-compatible rule record schema for Stage 2 → Stage 3 interop.

This schema is designed to be the bridge between our Stage 2 extraction
and Sun's Stage 3 compliance checking (Pair.py).

Key design decisions:
1. `obligation_lemmatized` is the primary field for similarity matching
   (equivalent to Sun's Clause.lemmatized)
2. `actor_canonical` is used for resource matching (equivalent to Sun's subject)
3. `order_relations` captures sequential flow (equivalent to Sun's Flow objects)
4. `actor_action_map` links actors to actions (equivalent to Sun's subject-verb-object)
5. All text fields are normalized (lowercase, lemmatized, stopwords removed)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class ActorActionMap:
    """Maps an actor to an action (subject → verb+object)."""

    actor: str
    action: str
    actor_canonical: str = ""  # normalized actor for matching
    action_canonical: str = ""  # normalized action for matching
    confidence: float = 1.0
    inferred: bool = False  # True if actor was inferred, not explicit


@dataclass
class OrderRelation:
    """Sequential order relation between two actions (then/after/before)."""

    first_action: str
    second_action: str
    marker: str  # "then", "after", "before", etc.
    confidence: float = 1.0


@dataclass
class ObligationRecord:
    """A single obligation extracted from a regulatory sentence.

    This is the primary unit for Stage 3 matching. Each obligation
    corresponds to one Clause in Sun's framework.
    """

    obligation_id: str
    source_text: str
    obligation_lemmatized: str  # ★ PRIMARY: bag-of-words for similarity matching
    modality: str  # obligation / prohibition / permission / definition
    actor: str  # raw actor text
    actor_canonical: str  # normalized actor for resource matching
    action: str  # raw action text
    action_canonical: str  # normalized action for matching
    condition: str = ""
    constraint: str = ""
    exception: str = ""
    actor_action_maps: list[ActorActionMap] = field(default_factory=list)
    order_relations: list[OrderRelation] = field(default_factory=list)
    confidence: float = 1.0
    provenance: str = "rule"  # rule / llm / merged
    validation_flags: dict[str, bool] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for JSONL output."""
        d = asdict(self)
        return d

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), ensure_ascii=False)


@dataclass
class SunRuleRecord:
    """Complete rule record from a single regulatory sentence.

    One sentence may produce multiple ObligationRecords (one per clause).
    This is the Stage 2 output that Stage 3 consumes.
    """

    rule_id: str
    source_text: str
    modality_type: str  # obligation / prohibition / permission / definition
    obligations: list[ObligationRecord] = field(default_factory=list)
    actors: list[str] = field(default_factory=list)  # all actors found
    actions: list[str] = field(default_factory=list)  # all actions found
    conditions: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    exceptions: list[str] = field(default_factory=list)
    order_relations: list[OrderRelation] = field(default_factory=list)
    actor_action_maps: list[ActorActionMap] = field(default_factory=list)
    provenance: str = "rule"
    confidence: float = 1.0
    validation_flags: dict[str, bool] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for JSONL output."""
        d = asdict(self)
        return d

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> SunRuleRecord:
        """Deserialize from dict."""
        obligations = [
            ObligationRecord(**o) for o in d.get("obligations", [])
        ]
        order_relations = [
            OrderRelation(**o) for o in d.get("order_relations", [])
        ]
        actor_action_maps = [
            ActorActionMap(**a) for a in d.get("actor_action_maps", [])
        ]
        return cls(
            rule_id=d["rule_id"],
            source_text=d["source_text"],
            modality_type=d["modality_type"],
            obligations=obligations,
            actors=d.get("actors", []),
            actions=d.get("actions", []),
            conditions=d.get("conditions", []),
            constraints=d.get("constraints", []),
            exceptions=d.get("exceptions", []),
            order_relations=order_relations,
            actor_action_maps=actor_action_maps,
            provenance=d.get("provenance", "rule"),
            confidence=d.get("confidence", 1.0),
            validation_flags=d.get("validation_flags", {}),
        )

    @classmethod
    def from_json(cls, json_str: str) -> SunRuleRecord:
        """Deserialize from JSON string."""
        return cls.from_dict(json.loads(json_str))
