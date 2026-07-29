"""Pre-result, method-independent G0.5 complexity profiling.

Text profiles consume a frozen/human-approved canonical annotation plus parser
structure. BPMN profiles consume only frozen input XML. Model predictions and
evaluation results are not accepted inputs, so method outputs cannot change a
sample's complexity stratum.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Mapping, Sequence
from xml.etree import ElementTree

from bpc_hybrid.stage2_canonical import validate_canonical


CONTRACT_SCHEMA = "complexity_contract@1.0.0"
PROFILE_SCHEMA = "complexity_profile@1.0.0"
PASSIVE_RELATIONS = {"nsubj:pass", "aux:pass", "nsubjpass", "auxpass"}
SCOPE_FIELDS = ("conditions", "constraints", "exceptions")
SEMANTIC_FIELDS = ("actors", "actions", *SCOPE_FIELDS)
ACTIVITY_TAGS = {
    "task",
    "userTask",
    "manualTask",
    "serviceTask",
    "scriptTask",
    "sendTask",
    "receiveTask",
    "businessRuleTask",
    "callActivity",
    "subProcess",
    "transaction",
}
EVENT_TAGS = {
    "startEvent",
    "endEvent",
    "intermediateCatchEvent",
    "intermediateThrowEvent",
    "boundaryEvent",
    "implicitThrowEvent",
}
GATEWAY_TAGS = {
    "exclusiveGateway",
    "inclusiveGateway",
    "parallelGateway",
    "complexGateway",
    "eventBasedGateway",
}
FLOW_NODE_TAGS = ACTIVITY_TAGS | EVENT_TAGS | GATEWAY_TAGS


class ComplexityContractError(ValueError):
    """Raised when a profile cannot be computed without violating G0.5."""


def load_complexity_contract(path: Path) -> dict[str, Any]:
    try:
        contract = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ComplexityContractError(f"invalid complexity contract: {path}") from exc
    if not isinstance(contract, dict):
        raise ComplexityContractError("complexity contract root must be an object")
    if (
        contract.get("schema_version") != CONTRACT_SCHEMA
        or contract.get("task_id") != "G0.5"
        or contract.get("status") != "preregistered_locked_before_complex_dataset_results"
    ):
        raise ComplexityContractError("complexity contract identity mismatch")
    leakage = contract.get("leakage_boundary", {})
    if (
        leakage.get("strata_frozen_before_method_outputs") is not True
        or leakage.get("missing_required_feature_policy") != "fail_closed_no_profile"
        or "model_prediction" not in leakage.get("forbidden_sources", ())
        or "test_result" not in leakage.get("forbidden_sources", ())
    ):
        raise ComplexityContractError("complexity leakage boundary changed")
    for domain, indicator_count, maximum in (("text", 11, 11), ("bpmn", 12, 12)):
        section = contract.get(domain, {})
        indicators = section.get("score_indicators", [])
        strata = section.get("strata", {})
        if len(indicators) != indicator_count or len({item.get("id") for item in indicators}) != indicator_count:
            raise ComplexityContractError(f"{domain} indicator registry changed")
        expected_ranges = {
            "low": (0, 3),
            "medium": (4, 7),
            "high": (8, maximum),
        }
        actual_ranges = {
            name: (strata.get(name, {}).get("min_score"), strata.get(name, {}).get("max_score"))
            for name in expected_ranges
        }
        if actual_ranges != expected_ranges:
            raise ComplexityContractError(f"{domain} strata changed")
    return contract


def validate_complexity_profile(profile: Mapping[str, Any], schema_path: Path) -> list[str]:
    try:
        schema = json.loads(Path(schema_path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ComplexityContractError(f"invalid complexity profile schema: {schema_path}") from exc
    try:
        import jsonschema
    except ImportError:
        required = {
            "schema_version", "item_id", "domain", "source_role", "metrics",
            "indicator_flags", "complexity_score", "complexity_stratum", "provenance",
        }
        return [] if isinstance(profile, Mapping) and set(profile) == required else ["minimal profile structure failed"]
    validator = jsonschema.Draft202012Validator(schema)
    return [
        f"{'.'.join(str(part) for part in error.path) or '<root>'}: {error.message}"
        for error in sorted(validator.iter_errors(dict(profile)), key=lambda item: list(item.path))
    ]


def _evaluate_indicators(metrics: Mapping[str, Any], indicators: Sequence[Mapping[str, Any]]) -> dict[str, bool]:
    result: dict[str, bool] = {}
    for indicator in indicators:
        indicator_id = indicator.get("id")
        operator = indicator.get("operator")
        if not isinstance(indicator_id, str) or not indicator_id:
            raise ComplexityContractError("indicator id must be non-empty")
        if operator == "ge":
            metric = indicator.get("metric")
            value = metrics.get(metric)
            threshold = indicator.get("threshold")
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ComplexityContractError(f"indicator metric is not numeric: {metric}")
            result[indicator_id] = value >= threshold
        elif operator == "sum_ge":
            names = indicator.get("metrics")
            if not isinstance(names, list) or not names:
                raise ComplexityContractError("sum_ge requires metric names")
            values = [metrics.get(name) for name in names]
            if any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in values):
                raise ComplexityContractError("sum_ge metric is not numeric")
            result[indicator_id] = sum(values) >= indicator.get("threshold")
        elif operator == "is_true":
            metric = indicator.get("metric")
            value = metrics.get(metric)
            if not isinstance(value, bool):
                raise ComplexityContractError(f"indicator metric is not boolean: {metric}")
            result[indicator_id] = value
        else:
            raise ComplexityContractError(f"unsupported indicator operator: {operator}")
    return result


def _stratum(score: int, strata: Mapping[str, Mapping[str, int]]) -> str:
    matches = [
        name for name, bounds in strata.items()
        if bounds["min_score"] <= score <= bounds["max_score"]
    ]
    if len(matches) != 1:
        raise ComplexityContractError(f"score {score} maps to {matches}, expected one stratum")
    return matches[0]


def _build_profile(
    *,
    item_id: str,
    domain: str,
    source_role: str,
    metrics: Mapping[str, Any],
    section: Mapping[str, Any],
) -> dict[str, Any]:
    flags = _evaluate_indicators(metrics, section["score_indicators"])
    score = sum(flags.values())
    return {
        "schema_version": PROFILE_SCHEMA,
        "item_id": item_id,
        "domain": domain,
        "source_role": source_role,
        "metrics": dict(metrics),
        "indicator_flags": flags,
        "complexity_score": score,
        "complexity_stratum": _stratum(score, section["strata"]),
        "provenance": {
            "contract_schema": CONTRACT_SCHEMA,
            "method_output_used": False,
            "result_used": False,
        },
    }


def _dependency_summary(sentence: Mapping[str, Any], source_text: str) -> tuple[int, bool, int]:
    tokens = sentence.get("tokens")
    dependencies = sentence.get("basicDependencies")
    if not isinstance(tokens, list) or not tokens or not isinstance(dependencies, list):
        raise ComplexityContractError("each text sentence requires tokens and basicDependencies")
    indexes = [token.get("index") for token in tokens]
    if indexes != list(range(1, len(tokens) + 1)):
        raise ComplexityContractError("token indexes must be contiguous and one-based")
    for token in tokens:
        start = token.get("characterOffsetBegin")
        end = token.get("characterOffsetEnd")
        word = token.get("word")
        if (
            isinstance(start, bool) or not isinstance(start, int)
            or isinstance(end, bool) or not isinstance(end, int)
            or not isinstance(word, str)
            or not (0 <= start < end <= len(source_text))
            or source_text[start:end] != word
        ):
            raise ComplexityContractError("token offsets do not match source_text")
    parent: dict[int, int] = {}
    passive = False
    for edge in dependencies:
        governor = edge.get("governor")
        dependent = edge.get("dependent")
        relation = edge.get("dep")
        if (
            isinstance(governor, bool) or not isinstance(governor, int)
            or isinstance(dependent, bool) or not isinstance(dependent, int)
            or dependent not in indexes
            or governor not in {0, *indexes}
            or dependent in parent
        ):
            raise ComplexityContractError("basicDependencies must define one valid parent per token")
        parent[dependent] = governor
        passive = passive or relation in PASSIVE_RELATIONS
    if set(parent) != set(indexes) or sum(governor == 0 for governor in parent.values()) != 1:
        raise ComplexityContractError("dependency tree must cover all tokens with exactly one root")

    memo: dict[int, int] = {}

    def depth(node: int, active: set[int]) -> int:
        if node in memo:
            return memo[node]
        if node in active:
            raise ComplexityContractError("dependency tree contains a cycle")
        governor = parent[node]
        value = 1 if governor == 0 else 1 + depth(governor, active | {node})
        memo[node] = value
        return value

    maximum = max(depth(index, set()) for index in indexes)
    return len(tokens), passive, maximum


def _scope_nesting_depth(clause: Mapping[str, Any]) -> int:
    spans = [
        (span["start"], span["end"])
        for field in SCOPE_FIELDS
        for span in clause.get(field, [])
    ]
    if not spans:
        return 0

    memo: dict[int, int] = {}

    def depth(index: int) -> int:
        if index in memo:
            return memo[index]
        start, end = spans[index]
        children = [
            other for other, (child_start, child_end) in enumerate(spans)
            if other != index
            and start <= child_start
            and child_end <= end
            and (start < child_start or child_end < end)
        ]
        value = 1 + max((depth(child) for child in children), default=0)
        memo[index] = value
        return value

    return max(depth(index) for index in range(len(spans)))


def profile_text_complexity(fixture: Mapping[str, Any], contract: Mapping[str, Any]) -> dict[str, Any]:
    item_id = fixture.get("item_id")
    source_role = fixture.get("source_role")
    source_text = fixture.get("source_text")
    if not isinstance(item_id, str) or not item_id or not isinstance(source_text, str) or not source_text:
        raise ComplexityContractError("text fixture requires item_id and source_text")
    allowed_roles = contract["leakage_boundary"]["allowed_text_semantic_roles"]
    if source_role not in allowed_roles:
        raise ComplexityContractError("text semantic source role is forbidden")
    record = fixture.get("canonical_record")
    if not isinstance(record, Mapping) or record.get("source_text") != source_text or record.get("sample_id") != item_id:
        raise ComplexityContractError("canonical text annotation is missing or misaligned")
    canonical_copy = copy.deepcopy(dict(record))
    report = validate_canonical(canonical_copy)
    if not (report.schema_valid and report.cross_field_valid):
        raise ComplexityContractError("canonical text annotation is invalid: " + "; ".join(report.errors))
    annotation = fixture.get("annotation")
    sentences = annotation.get("sentences") if isinstance(annotation, Mapping) else None
    if not isinstance(sentences, list) or not sentences:
        raise ComplexityContractError("text parser annotation has no sentences")
    dependency_summaries = [_dependency_summary(sentence, source_text) for sentence in sentences]

    clauses = canonical_copy["clauses"]
    counts = {
        field: sum(len(clause.get(field, [])) for clause in clauses)
        for field in SEMANTIC_FIELDS
    }
    actor_backed_actions = {
        edge.get("action_id")
        for clause in clauses
        for edge in clause.get("actor_action_map", [])
        if edge.get("actor_id") is not None
    }
    all_action_ids = {
        action["id"] for clause in clauses for action in clause.get("actions", [])
    }
    links = fixture.get("cross_sentence_reference_links")
    if not isinstance(links, list):
        raise ComplexityContractError("cross_sentence_reference_links must be explicitly supplied")
    unique_links: set[tuple[int, int, str]] = set()
    for link in links:
        if not isinstance(link, Mapping):
            raise ComplexityContractError("cross-sentence reference link must be an object")
        source_index = link.get("source_sentence_index")
        target_index = link.get("target_sentence_index")
        relation = link.get("relation")
        if (
            isinstance(source_index, bool) or not isinstance(source_index, int)
            or isinstance(target_index, bool) or not isinstance(target_index, int)
            or not (0 <= source_index < len(sentences))
            or not (0 <= target_index < len(sentences))
            or source_index == target_index
            or not isinstance(relation, str) or not relation
        ):
            raise ComplexityContractError("cross-sentence reference link is invalid")
        key = (source_index, target_index, relation)
        if key in unique_links:
            raise ComplexityContractError("duplicate cross-sentence reference link")
        unique_links.add(key)

    section = contract["text"]
    translation_status = fixture.get("translation_status")
    if translation_status not in section["translation_status_values"]:
        raise ComplexityContractError("translation_status is not registered")
    metrics = {
        "character_count": len(source_text),
        "token_count": sum(item[0] for item in dependency_summaries),
        "sentence_count": len(sentences),
        "clause_count": len(clauses),
        "max_dependency_depth": max(item[2] for item in dependency_summaries),
        "actor_count": counts["actors"],
        "action_count": counts["actions"],
        "condition_count": counts["conditions"],
        "constraint_count": counts["constraints"],
        "exception_count": counts["exceptions"],
        "semantic_span_count": sum(counts.values()),
        "scope_nesting_depth": max((_scope_nesting_depth(clause) for clause in clauses), default=0),
        "passive_voice_present": any(item[1] for item in dependency_summaries),
        "implicit_actor_action_count": len(all_action_ids - actor_backed_actions),
        "cross_sentence_reference_count": len(unique_links),
        "source_language": fixture.get("source_language"),
        "analysis_language": fixture.get("analysis_language"),
        "translation_status": translation_status,
    }
    if any(not isinstance(metrics[name], str) or len(metrics[name]) < 2 for name in ("source_language", "analysis_language")):
        raise ComplexityContractError("source_language and analysis_language are required")
    if tuple(metrics) != tuple(section["required_metrics"]):
        raise ComplexityContractError("computed text metric registry disagrees with contract")
    return _build_profile(
        item_id=item_id,
        domain="text",
        source_role=source_role,
        metrics=metrics,
        section=section,
    )


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _weak_component_count(nodes: set[str], edges: Sequence[tuple[str, str]]) -> int:
    adjacency = {node: set() for node in nodes}
    for source, target in edges:
        adjacency[source].add(target)
        adjacency[target].add(source)
    remaining = set(nodes)
    components = 0
    while remaining:
        components += 1
        stack = [remaining.pop()]
        while stack:
            neighbors = adjacency[stack.pop()] & remaining
            remaining.difference_update(neighbors)
            stack.extend(neighbors)
    return components


def _strong_components(nodes: set[str], edges: Sequence[tuple[str, str]]) -> list[set[str]]:
    adjacency = {node: [] for node in nodes}
    for source, target in edges:
        adjacency[source].append(target)
    next_index = 0
    indexes: dict[str, int] = {}
    lowlinks: dict[str, int] = {}
    stack: list[str] = []
    on_stack: set[str] = set()
    components: list[set[str]] = []

    def visit(node: str) -> None:
        nonlocal next_index
        indexes[node] = next_index
        lowlinks[node] = next_index
        next_index += 1
        stack.append(node)
        on_stack.add(node)
        for target in adjacency[node]:
            if target not in indexes:
                visit(target)
                lowlinks[node] = min(lowlinks[node], lowlinks[target])
            elif target in on_stack:
                lowlinks[node] = min(lowlinks[node], indexes[target])
        if lowlinks[node] == indexes[node]:
            component: set[str] = set()
            while True:
                member = stack.pop()
                on_stack.remove(member)
                component.add(member)
                if member == node:
                    break
            components.append(component)

    for node in sorted(nodes):
        if node not in indexes:
            visit(node)
    return components


def _condensation_summary(nodes: set[str], edges: Sequence[tuple[str, str]]) -> tuple[bool, int]:
    components = _strong_components(nodes, edges)
    component_index = {
        node: index for index, component in enumerate(components) for node in component
    }
    self_loops = {source for source, target in edges if source == target}
    cycle_present = bool(self_loops) or any(len(component) > 1 for component in components)
    dag = {index: set() for index in range(len(components))}
    for source, target in edges:
        source_component = component_index[source]
        target_component = component_index[target]
        if source_component != target_component:
            dag[source_component].add(target_component)
    memo: dict[int, int] = {}

    def depth(component: int) -> int:
        if component not in memo:
            memo[component] = 1 + max((depth(target) for target in dag[component]), default=0)
        return memo[component]

    return cycle_present, max(depth(index) for index in dag)


def profile_bpmn_complexity(
    *,
    item_id: str,
    xml_text: str,
    source_role: str,
    contract: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(item_id, str) or not item_id or not isinstance(xml_text, str) or not xml_text.strip():
        raise ComplexityContractError("BPMN profile requires item_id and XML text")
    if source_role not in contract["leakage_boundary"]["allowed_bpmn_input_roles"]:
        raise ComplexityContractError("BPMN input role is forbidden")
    if "<!DOCTYPE" in xml_text.upper() or "<!ENTITY" in xml_text.upper():
        raise ComplexityContractError("BPMN XML declarations with external entities are forbidden")
    try:
        root = ElementTree.fromstring(xml_text)
    except ElementTree.ParseError as exc:
        raise ComplexityContractError("BPMN XML is invalid") from exc
    elements = list(root.iter())
    flow_nodes: dict[str, str] = {}
    for element in elements:
        name = _local_name(element.tag)
        if name not in FLOW_NODE_TAGS:
            continue
        node_id = element.get("id")
        if not node_id or node_id in flow_nodes:
            raise ComplexityContractError("BPMN flow nodes require unique ids")
        flow_nodes[node_id] = name
    if not flow_nodes:
        raise ComplexityContractError("BPMN contains no supported flow nodes")
    edges: list[tuple[str, str]] = []
    for element in elements:
        if _local_name(element.tag) != "sequenceFlow":
            continue
        source = element.get("sourceRef")
        target = element.get("targetRef")
        if source not in flow_nodes or target not in flow_nodes:
            raise ComplexityContractError("sequenceFlow endpoints must reference supported flow nodes")
        edges.append((source, target))
    nodes = set(flow_nodes)
    weak_components = _weak_component_count(nodes, edges)
    out_degree = {node: 0 for node in nodes}
    in_degree = {node: 0 for node in nodes}
    for source, target in edges:
        out_degree[source] += 1
        in_degree[target] += 1
    cycle_present, condensation_depth = _condensation_summary(nodes, edges)
    section = contract["bpmn"]
    metrics = {
        "flow_node_count": len(nodes),
        "activity_count": sum(name in ACTIVITY_TAGS for name in flow_nodes.values()),
        "event_count": sum(name in EVENT_TAGS for name in flow_nodes.values()),
        "gateway_count": sum(name in GATEWAY_TAGS for name in flow_nodes.values()),
        "lane_count": sum(_local_name(element.tag) == "lane" for element in elements),
        "participant_count": sum(_local_name(element.tag) == "participant" for element in elements),
        "sequence_flow_count": len(edges),
        "message_flow_count": sum(_local_name(element.tag) == "messageFlow" for element in elements),
        "subprocess_count": sum(_local_name(element.tag) == "subProcess" for element in elements),
        "boundary_event_count": sum(_local_name(element.tag) == "boundaryEvent" for element in elements),
        "weak_component_count": weak_components,
        "cyclomatic_complexity": max(0, len(edges) - len(nodes) + 2 * weak_components),
        "branching_node_count": sum(value > 1 for value in out_degree.values()),
        "joining_node_count": sum(value > 1 for value in in_degree.values()),
        "cycle_present": cycle_present,
        "condensation_dag_depth": condensation_depth,
    }
    if tuple(metrics) != tuple(section["required_metrics"]):
        raise ComplexityContractError("computed BPMN metric registry disagrees with contract")
    return _build_profile(
        item_id=item_id,
        domain="bpmn",
        source_role=source_role,
        metrics=metrics,
        section=section,
    )

