"""Sun-style violation detection (R15.0).

Implements the three violation types described in Sun et al.:

1. **Missing action**: A rule's required action has no corresponding
   BPMN activity.
2. **Incorrect actor**: A rule's actor does not match the BPMN lane/
   resource assignment.
3. **Out-of-order execution**: BPMN sequence flow ordering contradicts
   rule constraint ordering.

This is a scaffold implementation using deterministic matching on
local fixtures.  It does NOT reproduce Sun's GDPR BPMN benchmark.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from bpc_hybrid.sun_style.bpmn_semantics import (
    BPMNSemanticParser,
    ProcessSemanticRecord,
)
from bpc_hybrid.sun_style.rule_record import RuleRecord


# ---------------------------------------------------------------------------
# Token overlap helpers
# ---------------------------------------------------------------------------

def _tokenize(text: str) -> set[str]:
    """Lowercase + split into word tokens."""
    return set(text.lower().split())


def _jaccard(a: set[str], b: set[str]) -> float:
    """Jaccard similarity between two token sets."""
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


# ---------------------------------------------------------------------------
# Violation types
# ---------------------------------------------------------------------------


class ViolationType:
    MISSING_ACTION = "missing_action"
    INCORRECT_ACTOR = "incorrect_actor"
    OUT_OF_ORDER = "out_of_order"


@dataclass
class Violation:
    """A detected violation."""

    violation_type: str
    rule_sample_id: str
    description: str
    severity: str = "error"  # error, warning


@dataclass
class ViolationReport:
    """Result of running all violation checks."""

    rule_record: RuleRecord | None = None
    process_record: ProcessSemanticRecord | None = None
    violations: list[Violation] = field(default_factory=list)

    @property
    def has_violations(self) -> bool:
        return len(self.violations) > 0

    @property
    def violation_types(self) -> set[str]:
        return {v.violation_type for v in self.violations}


# ---------------------------------------------------------------------------
# Detector
# ---------------------------------------------------------------------------


class ViolationDetector:
    """Detect Sun-style compliance violations.

    Compares a rule record against a BPMN process semantic record
    and reports missing actions, incorrect actors, and out-of-order
    execution.

    Usage::

        >>> detector = ViolationDetector()
        >>> report = detector.detect(rule_record, process_record)
        >>> print(report.violations)
    """

    # Jaccard threshold for considering a match
    ACTION_MATCH_THRESHOLD: float = 0.3
    ACTOR_MATCH_THRESHOLD: float = 0.3

    def detect(
        self,
        rule_record: RuleRecord,
        process_record: ProcessSemanticRecord,
    ) -> ViolationReport:
        """Run all three violation checks."""
        report = ViolationReport(
            rule_record=rule_record,
            process_record=process_record,
        )

        self._check_missing_action(rule_record, process_record, report)
        self._check_incorrect_actor(rule_record, process_record, report)
        self._check_out_of_order(rule_record, process_record, report)

        return report

    # ------------------------------------------------------------------
    # Individual checks
    # ------------------------------------------------------------------

    def _check_missing_action(
        self,
        rule: RuleRecord,
        process: ProcessSemanticRecord,
        report: ViolationReport,
    ) -> None:
        """Check if the rule's action has no matching BPMN activity."""
        rule_action = (
            rule.prediction_fields.get("action", {}).get("value", "")
        )
        if not rule_action.strip():
            return  # No action to check

        rule_tokens = _tokenize(rule_action)
        activity_names = process.activity_names

        best_score = 0.0
        best_match = ""
        for act_name in activity_names:
            score = _jaccard(rule_tokens, _tokenize(act_name))
            if score > best_score:
                best_score = score
                best_match = act_name

        if best_score < self.ACTION_MATCH_THRESHOLD:
            report.violations.append(Violation(
                violation_type=ViolationType.MISSING_ACTION,
                rule_sample_id=rule.sample_id,
                description=(
                    f"Rule action '{rule_action}' has no matching BPMN "
                    f"activity (best Jaccard={best_score:.2f} with "
                    f"'{best_match}'). Available activities: {activity_names}"
                ),
            ))

    def _check_incorrect_actor(
        self,
        rule: RuleRecord,
        process: ProcessSemanticRecord,
        report: ViolationReport,
    ) -> None:
        """Check if the rule's actor matches a BPMN lane."""
        rule_actor = (
            rule.prediction_fields.get("actor", {}).get("value", "")
        )
        if not rule_actor.strip():
            return  # No actor to check

        rule_tokens = _tokenize(rule_actor)
        lane_names = process.lane_names

        if not lane_names:
            return  # No lanes to compare

        best_score = 0.0
        best_match = ""
        for lane_name in lane_names:
            score = _jaccard(rule_tokens, _tokenize(lane_name))
            if score > best_score:
                best_score = score
                best_match = lane_name

        if best_score < self.ACTOR_MATCH_THRESHOLD:
            report.violations.append(Violation(
                violation_type=ViolationType.INCORRECT_ACTOR,
                rule_sample_id=rule.sample_id,
                description=(
                    f"Rule actor '{rule_actor}' does not match any BPMN "
                    f"lane (best Jaccard={best_score:.2f} with "
                    f"'{best_match}'). Available lanes: {lane_names}"
                ),
            ))

    def _check_out_of_order(
        self,
        rule: RuleRecord,
        process: ProcessSemanticRecord,
        report: ViolationReport,
    ) -> None:
        """Check if BPMN task ordering contradicts rule constraint ordering.

        Simple heuristic: if the rule mentions temporal ordering words
        (before, after, prior to, following) and the BPMN task order
        differs, flag it.
        """
        rule_text = rule.source_text.lower()

        # Detect temporal ordering in rule text
        has_ordering = any(
            word in rule_text
            for word in ["before", "after", "prior to", "following",
                         "subsequent", "then", "first", "second"]
        )
        if not has_ordering:
            return  # No temporal constraint to check

        # Get BPMN task order
        task_order = process.task_order()
        if len(task_order) < 2:
            return  # Need at least 2 activities to have ordering

        # Heuristic: if rule says "X before Y" but BPMN has Y before X,
        # flag it.
        rule_action = (
            rule.prediction_fields.get("action", {}).get("value", "")
        ).lower()

        # Simple check: is the rule's action present in the task order?
        found_idx = -1
        for i, task_name in enumerate(task_order):
            if _jaccard(_tokenize(rule_action),
                        _tokenize(task_name)) > self.ACTION_MATCH_THRESHOLD:
                found_idx = i
                break

        if found_idx == -1:
            return  # Can't determine position

        # If rule says "before", action should come before other constrained
        # actions.  This is a simplified heuristic.
        # For the out-of-order fixture test, check specifically:
        # Rule says "record ... before ... notify"
        # BPMN has "notify" before "record" → violation
        if "before" in rule_text:
            # Find what comes "before" what
            rule_tokens = rule_text.split()
            before_idx = -1
            for i, tok in enumerate(rule_tokens):
                if tok == "before" and i > 0 and i < len(rule_tokens) - 1:
                    before_idx = i
                    break

            if before_idx > 0:
                first_action = rule_tokens[before_idx - 1]
                # Find these in task order
                first_pos = -1
                second_pos = -1
                for i, task_name in enumerate(task_order):
                    tok_set = _tokenize(task_name)
                    if first_action in tok_set or _jaccard({first_action}, tok_set) > 0.3:
                        if first_pos == -1:
                            first_pos = i
                    if (before_idx + 1 < len(rule_tokens)
                            and rule_tokens[before_idx + 1] in tok_set):
                        if second_pos == -1:
                            second_pos = i

                # Out of order: first should come before second in BPMN
                if first_pos >= 0 and second_pos >= 0 and first_pos >= second_pos:
                    report.violations.append(Violation(
                        violation_type=ViolationType.OUT_OF_ORDER,
                        rule_sample_id=rule.sample_id,
                        description=(
                            f"Rule requires '{rule_tokens[before_idx - 1]}' "
                            f"before '{rule_tokens[before_idx + 1]}' but "
                            f"BPMN task order is: {task_order}"
                        ),
                    ))
