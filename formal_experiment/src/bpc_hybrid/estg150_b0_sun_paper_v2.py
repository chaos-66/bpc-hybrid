"""Isolated Sun Section 4.2.2 rule-semantics correction for the mini pipeline.

This module does not replace the earlier development runner.  It supplies a
second rule-plan writer, a root-bound actor dependency gate, and an independent
context-capture bridge so the small regression pipeline can verify the change
before any new 150-record run is considered.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Mapping, Sequence

from bpc_hybrid.estg150_b0_development import Estg150B0DevelopmentError
from bpc_hybrid.estg150_b0_sun_paper import (
    PAPER_ORDER,
    _marker_tokens,
    run_b0_batch_sun_paper,
)


METHOD_VARIANT = "b0_sun_paper_semantics_v2"
BRIDGE_CLASS = "SunPaperIndependentContextBridge"
BRIDGE_REL = "tools/corenlp/SunPaperIndependentContextBridge.java"


def _leaf_predicate(token: str) -> str:
    escaped = re.escape(token).replace("/", r"\/")
    return f" < /(?i)^{escaped}$/"


def _descendant_predicates(tokens: Sequence[str]) -> str:
    result: list[str] = []
    for token in tokens:
        escaped = re.escape(token).replace("/", r"\/")
        result.append(f" << /(?i)^{escaped}$/")
    return "".join(result)


def write_semantics_v2_rule_plan(
    registry: Mapping[str, Any],
    markers: Mapping[str, Sequence[str]],
    target: Path,
) -> int:
    """Compile Sun's published < versus << relations without cross-field pruning."""

    if tuple(registry.get("extraction_order", ())) != PAPER_ORDER:
        raise Estg150B0DevelopmentError("Sun paper extraction dependency changed")
    fields = registry.get("fields")
    if not isinstance(fields, Mapping):
        raise Estg150B0DevelopmentError("Sun paper rule registry fields missing")
    lines: list[str] = []

    def add(field: str, pattern: str, operation: str | None) -> None:
        if "\t" in pattern or "\n" in pattern:
            raise Estg150B0DevelopmentError("Tregex pattern is not plan-safe")
        lines.append(f"{field}\t{pattern}\t{operation or ''}")

    for pattern in fields["modality"]["tregex_patterns"]:
        add("modality", pattern, fields["modality"]["tsurgeon_operation"])

    for surface in markers["condition"]:
        predicates = _descendant_predicates(_marker_tokens(surface))
        for template in fields["condition"]["tregex_templates"]:
            add(
                "condition",
                template.replace("{marker_predicates}", predicates),
                fields["condition"]["tsurgeon_operation"],
            )

    for surface in markers["constraint"]:
        tokens = _marker_tokens(surface)
        remaining = _descendant_predicates(tokens[1:])
        add(
            "constraint",
            fields["constraint"]["tregex_templates"][0]
            .replace("{first_marker_leaf}", _leaf_predicate(tokens[0]))
            .replace("{remaining_marker_predicates}", remaining),
            fields["constraint"]["tsurgeon_operation"],
        )
        add(
            "constraint",
            fields["constraint"]["tregex_templates"][1]
            .replace("{first_marker_leaf}", _leaf_predicate(tokens[0]))
            .replace("{remaining_marker_predicates}", remaining),
            fields["constraint"]["tsurgeon_operation"],
        )

    for surface in markers["exception"]:
        tokens = _marker_tokens(surface)
        predicates = _descendant_predicates(tokens)
        remaining = _descendant_predicates(tokens[1:])
        add(
            "exception",
            fields["exception"]["tregex_templates"][0].replace(
                "{marker_predicates}", predicates
            ),
            fields["exception"]["tsurgeon_operation"],
        )
        add(
            "exception",
            fields["exception"]["tregex_templates"][1].replace(
                "{marker_predicates}", predicates
            ),
            fields["exception"]["tsurgeon_operation"],
        )
        add(
            "exception",
            fields["exception"]["tregex_templates"][2]
            .replace("{first_marker_leaf}", _leaf_predicate(tokens[0]))
            .replace("{remaining_marker_predicates}", remaining),
            fields["exception"]["tsurgeon_operation"],
        )

    for surface in markers["actor"]:
        tokens = _marker_tokens(surface)
        add(
            "actor",
            fields["actor"]["candidate_template"]
            .replace("{first_marker_leaf}", _leaf_predicate(tokens[0]))
            .replace(
                "{remaining_marker_predicates}",
                _descendant_predicates(tokens[1:]),
            ),
            None,
        )

    for pattern in fields["action"]["tregex_patterns"]:
        add("action", pattern, None)

    target.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return len(lines)


def actor_dependency_supported_by_clause_relation(
    sentence: Mapping[str, Any], observation: Mapping[str, Any]
) -> bool:
    """Apply Sun's subject/object and same-governor active/passive actor rules."""

    begin = observation.get("begin")
    end = observation.get("end")
    tokens = sentence.get("tokens")
    dependencies = sentence.get("basicDependencies")
    if (
        not isinstance(begin, int)
        or not isinstance(end, int)
        or not isinstance(tokens, list)
        or not isinstance(dependencies, list)
    ):
        return False
    passive_governors = {
        dep.get("governor")
        for dep in dependencies
        if isinstance(dep, Mapping)
        and str(dep.get("dep", "")).casefold() in {"auxpass", "aux:pass"}
        and isinstance(dep.get("governor"), int)
    }
    in_pp = begin > 0 and str(tokens[begin - 1].get("pos", "")).upper() == "IN"
    for dep in dependencies:
        if not isinstance(dep, Mapping):
            continue
        relation = str(dep.get("dep", "")).casefold()
        dependent = dep.get("dependent")
        governor = dep.get("governor")
        if (
            not isinstance(dependent, int)
            or not isinstance(governor, int)
            or not (begin <= dependent - 1 < end)
        ):
            continue
        if relation.startswith("nsubj"):
            return True
        if governor in passive_governors and in_pp and (
            relation.startswith("obl")
            or relation.startswith("nmod")
            or "obj" in relation
            or relation == "agent"
        ):
            return True
        if governor not in passive_governors and relation in {"obj", "dobj", "iobj"}:
            return True
    return False


def run_b0_batch_sun_semantics_v2(
    project_root: Path,
    source_records: Sequence[Mapping[str, Any]],
    *,
    runtime_home: Path,
    work_dir: Path,
    s26_config_rel: str,
    registry_rel: str,
    marker_specs: Mapping[str, Mapping[str, Any]],
    device: str = "cpu",
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Run the isolated v2 semantics through the unchanged B0 composition seam."""

    return run_b0_batch_sun_paper(
        project_root,
        source_records,
        runtime_home=runtime_home,
        work_dir=work_dir,
        s26_config_rel=s26_config_rel,
        registry_rel=registry_rel,
        marker_specs=marker_specs,
        device=device,
        actor_dependency_gate=actor_dependency_supported_by_clause_relation,
        rule_plan_writer=write_semantics_v2_rule_plan,
        bridge_class=BRIDGE_CLASS,
        bridge_rel=BRIDGE_REL,
        method_variant=METHOD_VARIANT,
        paper_faithful_reconstruction=False,
    )
