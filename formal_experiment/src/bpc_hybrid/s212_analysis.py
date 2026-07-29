"""Pre-result S2.12 complexity and error-analysis mechanics."""

from __future__ import annotations

import hashlib
import json
import math
import random
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


class S212AnalysisError(ValueError):
    """Raised when the pre-registered analysis contract is violated."""


FORMAL_METHODS = ("sun_rule_only", "sun_llm_fallback", "direct_llm")
STRATA = ("low", "medium", "high")
AGGREGATIONS = {"macro_f1", "micro_f1"}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_analysis_protocol(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise S212AnalysisError(f"invalid S2.12 protocol JSON: {path}") from exc
    if not isinstance(value, dict):
        raise S212AnalysisError("S2.12 protocol root must be an object")
    _validate_protocol(value)
    return value


def _validate_protocol(protocol: Mapping[str, Any]) -> None:
    if protocol.get("schema_version") != "s212_analysis_protocol@1.1.0":
        raise S212AnalysisError("unexpected S2.12 protocol version")
    if protocol.get("task_id") != "S2.12-P":
        raise S212AnalysisError("unexpected S2.12 task id")
    methods = protocol.get("methods", {})
    if tuple(methods.get("formal", ())) != FORMAL_METHODS:
        raise S212AnalysisError("formal method order changed")
    if methods.get("reference_method") != FORMAL_METHODS[0]:
        raise S212AnalysisError("reference method must be sun_rule_only")
    contrasts = methods.get("contrasts")
    expected_contrasts = (
        ("h1_minus_b0", "sun_llm_fallback", "sun_rule_only"),
        ("d1_minus_b0", "direct_llm", "sun_rule_only"),
    )
    actual_contrasts = tuple(
        (item.get("id"), item.get("candidate"), item.get("reference"))
        for item in contrasts or ()
        if isinstance(item, Mapping)
    )
    if actual_contrasts != expected_contrasts:
        raise S212AnalysisError("primary contrasts changed")
    stratification = protocol.get("complexity_stratification", {})
    if tuple(stratification.get("strata_order", ())) != STRATA:
        raise S212AnalysisError("complexity strata changed")
    if stratification.get("text_score_ranges") != {
        "low": [0, 3],
        "medium": [4, 7],
        "high": [8, 11],
    }:
        raise S212AnalysisError("G0.5 text score ranges changed")
    if stratification.get("method_specific_rebinning_allowed") is not False:
        raise S212AnalysisError("method-specific rebinning must be forbidden")
    endpoints = protocol.get("primary_endpoints")
    if not isinstance(endpoints, list) or len(endpoints) != 6:
        raise S212AnalysisError("exactly six primary endpoints are required")
    endpoint_ids: set[str] = set()
    for endpoint in endpoints:
        if not isinstance(endpoint, Mapping):
            raise S212AnalysisError("primary endpoint must be an object")
        endpoint_id = endpoint.get("id")
        components = endpoint.get("components")
        if not isinstance(endpoint_id, str) or endpoint_id in endpoint_ids:
            raise S212AnalysisError("primary endpoint ids must be unique strings")
        if endpoint.get("aggregation") not in AGGREGATIONS:
            raise S212AnalysisError("unsupported endpoint aggregation")
        if not isinstance(components, list) or not components or len(set(components)) != len(components):
            raise S212AnalysisError("endpoint components must be a non-empty unique list")
        endpoint_ids.add(endpoint_id)
    statistics = protocol.get("statistics", {})
    if statistics.get("confidence_interval", {}).get("iterations") != 10000:
        raise S212AnalysisError("bootstrap iterations must remain 10000")
    if statistics.get("hypothesis_test", {}).get("iterations") != 10000:
        raise S212AnalysisError("randomization iterations must remain 10000")
    if statistics.get("multiplicity", {}).get("hypotheses_per_family") != 12:
        raise S212AnalysisError("Holm family must contain 12 hypotheses per dataset")
    if protocol.get("analysis_units", {}).get(
        "missing_invalid_and_api_error_records_remain_in_denominator"
    ) is not True:
        raise S212AnalysisError("failed records must remain in the denominator")
    priority = protocol.get("error_analysis", {}).get("primary_priority")
    if not isinstance(priority, list) or len(priority) != len(set(priority)) or not priority:
        raise S212AnalysisError("error priority must be a non-empty unique list")


def _seed(base: str, *parts: str) -> int:
    payload = "|".join((base, *parts)).encode("utf-8")
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")


def _f1(tp: float, fp: float, fn: float) -> float:
    denominator = 2.0 * tp + fp + fn
    return 0.0 if denominator == 0.0 else 2.0 * tp / denominator


def _validate_count_payload(
    payload: Mapping[str, Any], endpoint: Mapping[str, Any]
) -> None:
    components = endpoint["components"]
    if set(payload) != set(components):
        raise S212AnalysisError(f"component registry mismatch for {endpoint['id']}")
    for component in components:
        triple = payload[component]
        if (
            not isinstance(triple, list)
            or len(triple) != 3
            or any(
                not isinstance(value, (int, float))
                or isinstance(value, bool)
                or not math.isfinite(float(value))
                or value < 0
                for value in triple
            )
        ):
            raise S212AnalysisError("metric sufficient statistics must be non-negative [tp, fp, fn]")


def validate_observations(
    observations: Sequence[Mapping[str, Any]], protocol: Mapping[str, Any]
) -> list[Mapping[str, Any]]:
    _validate_protocol(protocol)
    if not isinstance(observations, Sequence) or isinstance(observations, (str, bytes)) or not observations:
        raise S212AnalysisError("observations must be a non-empty sequence")
    allowed_roles = set(protocol["complexity_stratification"]["profile_source_roles"])
    forbidden = set(protocol["leakage_boundary"]["forbidden_stratification_inputs"])
    endpoint_map = {item["id"]: item for item in protocol["primary_endpoints"]}
    seen: set[str] = set()
    validated: list[Mapping[str, Any]] = []
    for row in observations:
        if not isinstance(row, Mapping):
            raise S212AnalysisError("observation must be an object")
        if forbidden.intersection(row):
            raise S212AnalysisError("forbidden result-derived stratification input")
        sample_id = row.get("sample_id")
        if not isinstance(sample_id, str) or not sample_id or sample_id in seen:
            raise S212AnalysisError("sample_id must be a unique non-empty string")
        if row.get("profile_source_role") not in allowed_roles:
            raise S212AnalysisError("complexity profile source role is not allowed")
        if row.get("stratum") not in STRATA:
            raise S212AnalysisError("observation uses an unknown fixed stratum")
        methods = row.get("methods")
        if not isinstance(methods, Mapping) or set(methods) != set(FORMAL_METHODS):
            raise S212AnalysisError("every observation must contain all three formal methods")
        for method in FORMAL_METHODS:
            metrics = methods[method]
            if not isinstance(metrics, Mapping) or set(metrics) != set(endpoint_map):
                raise S212AnalysisError("method endpoint registry mismatch")
            for endpoint_id, endpoint in endpoint_map.items():
                payload = metrics[endpoint_id]
                if not isinstance(payload, Mapping):
                    raise S212AnalysisError("endpoint payload must be an object")
                _validate_count_payload(payload, endpoint)
        seen.add(sample_id)
        validated.append(row)
    return sorted(validated, key=lambda item: item["sample_id"])


def _metric_from_payloads(
    payloads: Iterable[Mapping[str, Sequence[float]]], endpoint: Mapping[str, Any]
) -> float:
    totals = {component: [0.0, 0.0, 0.0] for component in endpoint["components"]}
    for payload in payloads:
        for component in endpoint["components"]:
            triple = payload[component]
            for index in range(3):
                totals[component][index] += float(triple[index])
    if endpoint["aggregation"] == "macro_f1":
        return sum(_f1(*totals[component]) for component in endpoint["components"]) / len(
            endpoint["components"]
        )
    tp = sum(totals[component][0] for component in endpoint["components"])
    fp = sum(totals[component][1] for component in endpoint["components"])
    fn = sum(totals[component][2] for component in endpoint["components"])
    return _f1(tp, fp, fn)


def _metric(
    observations: Sequence[Mapping[str, Any]], method: str, endpoint: Mapping[str, Any]
) -> float:
    return _metric_from_payloads(
        (row["methods"][method][endpoint["id"]] for row in observations), endpoint
    )


def _percentile_type7(values: Sequence[float], quantile: float) -> float:
    if not values or not 0.0 <= quantile <= 1.0:
        raise S212AnalysisError("percentile input is invalid")
    ordered = sorted(values)
    position = (len(ordered) - 1) * quantile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def _paired_bootstrap_delta(
    observations: Sequence[Mapping[str, Any]],
    endpoint: Mapping[str, Any],
    candidate: str,
    reference: str,
    *,
    iterations: int,
    seed: int,
) -> list[float]:
    rng = random.Random(seed)
    sample_count = len(observations)
    deltas: list[float] = []
    for _ in range(iterations):
        sampled = [observations[rng.randrange(sample_count)] for _ in range(sample_count)]
        deltas.append(_metric(sampled, candidate, endpoint) - _metric(sampled, reference, endpoint))
    return deltas


def _paired_randomization_p_value(
    observations: Sequence[Mapping[str, Any]],
    endpoint: Mapping[str, Any],
    candidate: str,
    reference: str,
    observed_delta: float,
    *,
    iterations: int,
    seed: int,
) -> float:
    rng = random.Random(seed)
    endpoint_id = endpoint["id"]
    extreme = 0
    tolerance = 1e-15
    for _ in range(iterations):
        candidate_payloads = []
        reference_payloads = []
        for row in observations:
            candidate_payload = row["methods"][candidate][endpoint_id]
            reference_payload = row["methods"][reference][endpoint_id]
            if rng.getrandbits(1):
                candidate_payload, reference_payload = reference_payload, candidate_payload
            candidate_payloads.append(candidate_payload)
            reference_payloads.append(reference_payload)
        randomized_delta = _metric_from_payloads(candidate_payloads, endpoint) - _metric_from_payloads(
            reference_payloads, endpoint
        )
        if abs(randomized_delta) + tolerance >= abs(observed_delta):
            extreme += 1
    return (extreme + 1.0) / (iterations + 1.0)


def holm_adjust(p_values: Mapping[str, float], *, alpha: float) -> dict[str, dict[str, Any]]:
    if not p_values:
        raise S212AnalysisError("Holm adjustment requires at least one p-value")
    if not 0.0 < alpha < 1.0:
        raise S212AnalysisError("Holm alpha must be between zero and one")
    for value in p_values.values():
        if not isinstance(value, (int, float)) or isinstance(value, bool) or not 0.0 <= value <= 1.0:
            raise S212AnalysisError("p-values must be finite values in [0, 1]")
    ordered = sorted(p_values.items(), key=lambda item: (item[1], item[0]))
    family_size = len(ordered)
    adjusted: dict[str, dict[str, Any]] = {}
    running = 0.0
    for rank, (hypothesis_id, raw_p) in enumerate(ordered, start=1):
        running = max(running, min(1.0, (family_size - rank + 1) * float(raw_p)))
        adjusted[hypothesis_id] = {
            "raw_p": float(raw_p),
            "holm_adjusted_p": running,
            "reject_at_alpha": running <= alpha,
            "rank": rank,
        }
    return {hypothesis_id: adjusted[hypothesis_id] for hypothesis_id in sorted(adjusted)}


def analyze_primary_family(
    observations: Sequence[Mapping[str, Any]],
    protocol: Mapping[str, Any],
    *,
    dataset_id: str,
) -> dict[str, Any]:
    rows = validate_observations(observations, protocol)
    endpoint_map = {item["id"]: item for item in protocol["primary_endpoints"]}
    ci = protocol["statistics"]["confidence_interval"]
    test = protocol["statistics"]["hypothesis_test"]
    alpha = float(protocol["statistics"]["multiplicity"]["alpha"])
    hypotheses: dict[str, dict[str, Any]] = {}
    raw_p_values: dict[str, float] = {}
    for contrast in protocol["methods"]["contrasts"]:
        for endpoint_id, endpoint in endpoint_map.items():
            hypothesis_id = f"{contrast['id']}::{endpoint_id}"
            candidate_point = _metric(rows, contrast["candidate"], endpoint)
            reference_point = _metric(rows, contrast["reference"], endpoint)
            observed_delta = candidate_point - reference_point
            bootstrap_deltas = _paired_bootstrap_delta(
                rows,
                endpoint,
                contrast["candidate"],
                contrast["reference"],
                iterations=int(ci["iterations"]),
                seed=_seed(ci["seed"], dataset_id, hypothesis_id),
            )
            raw_p = _paired_randomization_p_value(
                rows,
                endpoint,
                contrast["candidate"],
                contrast["reference"],
                observed_delta,
                iterations=int(test["iterations"]),
                seed=_seed(test["seed"], dataset_id, hypothesis_id),
            )
            raw_p_values[hypothesis_id] = raw_p
            hypotheses[hypothesis_id] = {
                "contrast": contrast["id"],
                "endpoint": endpoint_id,
                "candidate_point": candidate_point,
                "reference_point": reference_point,
                "delta": observed_delta,
                "delta_ci_low": _percentile_type7(bootstrap_deltas, (1.0 - float(ci["level"])) / 2.0),
                "delta_ci_high": _percentile_type7(bootstrap_deltas, 1.0 - (1.0 - float(ci["level"])) / 2.0),
                "raw_p": raw_p,
            }
    adjusted = holm_adjust(raw_p_values, alpha=alpha)
    for hypothesis_id, values in adjusted.items():
        hypotheses[hypothesis_id].update(values)
    return {
        "dataset_id": dataset_id,
        "sample_count": len(rows),
        "hypothesis_count": len(hypotheses),
        "holm_family_size": len(hypotheses),
        "hypotheses": {key: hypotheses[key] for key in sorted(hypotheses)},
    }


def summarize_strata(
    observations: Sequence[Mapping[str, Any]],
    protocol: Mapping[str, Any],
    *,
    method: str,
    endpoint_id: str,
) -> dict[str, dict[str, Any]]:
    rows = validate_observations(observations, protocol)
    if method not in FORMAL_METHODS:
        raise S212AnalysisError("unknown formal method")
    endpoint_map = {item["id"]: item for item in protocol["primary_endpoints"]}
    if endpoint_id not in endpoint_map:
        raise S212AnalysisError("unknown primary endpoint")
    minimum = int(protocol["complexity_stratification"]["minimum_cluster_count_for_interval"])
    result: dict[str, dict[str, Any]] = {}
    for stratum in STRATA:
        selected = [row for row in rows if row["stratum"] == stratum]
        result[stratum] = {
            "sample_count": len(selected),
            "point_estimate": _metric(selected, method, endpoint_map[endpoint_id]) if selected else None,
            "interval_estimable": len(selected) >= minimum,
            "interval": None,
        }
    return result


def assign_error_categories(
    categories: Sequence[str], protocol: Mapping[str, Any]
) -> dict[str, Any]:
    _validate_protocol(protocol)
    if not isinstance(categories, Sequence) or isinstance(categories, (str, bytes)) or not categories:
        raise S212AnalysisError("at least one error category is required")
    priority = protocol["error_analysis"]["primary_priority"]
    allowed = set(priority)
    unique = set(categories)
    if not unique.issubset(allowed):
        raise S212AnalysisError("unknown error category")
    ordered = [category for category in priority if category in unique]
    return {"primary": ordered[0], "all": ordered}


def select_qualitative_cases(
    cases: Sequence[Mapping[str, Any]], protocol: Mapping[str, Any]
) -> list[dict[str, Any]]:
    _validate_protocol(protocol)
    selection = protocol["error_analysis"]["qualitative_case_selection"]
    limit = int(selection["cases_per_dataset_method_primary_category"])
    seed = selection["seed"]
    ranked: dict[tuple[str, str, str], list[tuple[str, str]]] = {}
    for case in cases:
        if not isinstance(case, Mapping):
            raise S212AnalysisError("qualitative case must be an object")
        dataset_id = case.get("dataset_id")
        method = case.get("method")
        category = case.get("primary_category")
        sample_id = case.get("sample_id")
        if method not in FORMAL_METHODS or category not in protocol["error_analysis"]["primary_priority"]:
            raise S212AnalysisError("qualitative case method or category is invalid")
        if not all(isinstance(value, str) and value for value in (dataset_id, sample_id)):
            raise S212AnalysisError("qualitative case identity is invalid")
        rank = hashlib.sha256(
            "|".join((seed, dataset_id, method, category, sample_id)).encode("utf-8")
        ).hexdigest()
        ranked.setdefault((dataset_id, method, category), []).append((rank, sample_id))
    selected: list[dict[str, Any]] = []
    for key in sorted(ranked):
        for rank, sample_id in sorted(ranked[key])[:limit]:
            selected.append(
                {
                    "dataset_id": key[0],
                    "method": key[1],
                    "primary_category": key[2],
                    "sample_id": sample_id,
                    "selection_rank_sha256": rank,
                }
            )
    return selected
