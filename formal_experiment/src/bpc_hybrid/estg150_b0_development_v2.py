"""EStG-150 B0 enhanced development batch (versioned, non-paper-faithful claim).

Fixes vs locked B0 v1:
1. Clause/sentence-level German modality classification (no record label replication)
2. English public-marker override when DE alignment is ambiguous
3. CoreNLP sentence merge/split for better clause segmentation
4. Multi non-overlapping phrase matches per field
5. Narrower actor spans and expanded condition/constraint/exception patterns

Does not modify Layer E / Gold, does not call LLM/API, does not overwrite v1 outputs.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

from bpc_hybrid.estg150_b0_development import (
    Estg150B0DevelopmentError,
    build_canonical_gold_records,
    load_jsonl,
    load_object,
    sha256_file,
    summarize_evaluation,
)
from bpc_hybrid.stage2_canonical import SCHEMA_SOURCE, SCHEMA_VERSION, validate_canonical
from bpc_hybrid.sun_style.corenlp_runtime import (
    EXTRACTION_ORDER,
    CoreNLPContractError,
    resolve_corenlp_runtime,
    validate_annotation,
)
from bpc_hybrid.sun_style.sun_b0 import (
    LockedBertTextCNNInference,
    ModalityPrediction,
    SunB0CompositionError,
    load_s26_config,
)

METHOD_ID = "sun_rule_only"
METHOD_VARIANT = "b0_enhanced"
BRIDGE_CLASS = "SunPhraseRuleBatchBridgeMulti"
PATTERNS_REL = "resources/corenlp/sun_phrase_patterns_v2_enhanced.json"
BRIDGE_REL = "tools/corenlp/SunPhraseRuleBatchBridgeMulti.java"

_EN_PROHIBITION = re.compile(
    r"\b(?:shall\s+not|must\s+not|may\s+not|is\s+not\s+permitted|is\s+prohibited|"
    r"is\s+not\s+allowed|no\s+\w+\s+shall)\b",
    re.IGNORECASE,
)
_EN_OBLIGATION = re.compile(
    r"\b(?:shall|must|is\s+required\s+to|is\s+obliged\s+to|need\s+to)\b",
    re.IGNORECASE,
)
_EN_PERMISSION = re.compile(
    r"\b(?:may|is\s+permitted\s+to|is\s+allowed\s+to|is\s+authorized\s+to|can)\b",
    re.IGNORECASE,
)
_EN_DEFINITION = re.compile(
    r"\b(?:means|is\s+defined\s+as|refers\s+to|denotes|is\s+understood\s+as|"
    r"shall\s+mean|prerequisite\s+for)\b",
    re.IGNORECASE,
)
_DE_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z\u00c4\u00d6\u00dc\"(0-9])")
_LIST_CONTINUATION = re.compile(
    r"^(?:\d+[\.\)]\s*[a-z]?\)?|[a-z]\)|\u2014|-|;|,)\s*",
    re.IGNORECASE,
)
_COORD_MODALITY = re.compile(
    r"\b(?:and|or|but|however|;)\s+(?=(?:the\s+)?(?:taxpayer|employee|employer|authority|"
    r"fund|person|it|he|she|they|this|these|those)\b|"
    r"(?:shall|must|may|shall\s+not|must\s+not|may\s+not)\b)",
    re.IGNORECASE,
)
_PRONOUN_ACTORS = frozenset({"it", "this", "these", "those", "they", "he", "she", "we", "i"})
_ACTOR_MAX_TOKENS = 12
_ACTOR_SURFACES = frozenset({
    "taxpayer", "taxpayers", "employee", "employees", "employer", "employers",
    "authority", "authorities", "fund", "funds", "controller", "processor",
    "person", "persons", "company", "companies", "operator", "operators",
    "user", "users", "recipient", "recipients", "minister", "office",
    "association", "associations", "farmer", "farmers", "forester", "foresters",
    "trader", "traders", "successor", "successors", "insured", "provider",
})



def _run(command: Sequence[str], *, cwd: Path, timeout: int) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        list(command),
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )
    if completed.returncode != 0:
        detail = (completed.stdout + "\n" + completed.stderr)[-5000:]
        raise Estg150B0DevelopmentError(
            f"offline command failed ({completed.returncode}): {command[0]}\n{detail}"
        )
    return completed


def _write_rule_plan(registry: Mapping[str, Any], target: Path) -> int:
    if tuple(registry.get("extraction_order", ())) != EXTRACTION_ORDER:
        raise Estg150B0DevelopmentError("CoreNLP extraction order changed")
    fields = registry.get("fields")
    if not isinstance(fields, list):
        raise Estg150B0DevelopmentError("rule registry fields missing")
    lines: list[str] = []
    for item in fields:
        operations = item.get("tsurgeon_operations")
        patterns = item.get("tregex_patterns")
        if not isinstance(operations, list) or len(operations) > 1:
            raise Estg150B0DevelopmentError("invalid Tsurgeon operation count")
        if not isinstance(patterns, list) or not patterns:
            raise Estg150B0DevelopmentError("Tregex pattern list missing")
        operation = operations[0] if operations else ""
        for pattern in patterns:
            if not isinstance(pattern, str) or "\t" in pattern or "\n" in pattern:
                raise Estg150B0DevelopmentError("Tregex pattern is not plan-safe")
            lines.append(f"{item['field']}\t{pattern}\t{operation}")
    target.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return len(lines)


def parse_bridge_output_multi(output: str) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Parse multi-match bridge output; fields hold lists of matches."""
    cases: dict[int, dict[str, list[dict[str, Any]]]] = {}
    summary: dict[str, int] | None = None
    for raw in output.splitlines():
        parts = raw.split("\t")
        if parts[0] == "MATCH" and len(parts) == 8:
            index = int(parts[1])
            fields = cases.setdefault(index, {field: [] for field in EXTRACTION_ORDER})
            fields[parts[2]].append(
                {
                    "begin": int(parts[3]),
                    "end": int(parts[4]),
                    "text": parts[5],
                    "pattern_index": int(parts[6]),
                    "operation_applied": parts[7] == "true",
                }
            )
        elif parts[0] == "MISS" and len(parts) == 3:
            index = int(parts[1])
            cases.setdefault(index, {field: [] for field in EXTRACTION_ORDER})
        elif parts[0] == "TERMINAL_TREE_REMOVALS" and len(parts) == 2:
            if summary is None:
                summary = {}
            summary["terminal_tree_removal_count"] = int(parts[1])
        elif parts[0] == "SUMMARY" and len(parts) == 5:
            terminal_count = 0 if summary is None else summary.get(
                "terminal_tree_removal_count", 0
            )
            summary = {
                "tree_count": int(parts[1]),
                "pattern_count": int(parts[2]),
                "match_count": int(parts[3]),
                "surgery_count": int(parts[4]),
                "terminal_tree_removal_count": terminal_count,
            }
    if summary is None:
        raise Estg150B0DevelopmentError("Java bridge did not emit SUMMARY")
    ordered = [
        {"sentence_index": index, "fields": cases[index]}
        for index in sorted(cases)
    ]
    return ordered, summary


def english_marker_modality(text: str) -> str | None:
    """Public English marker priority: prohibition > obligation > permission > definition."""
    if _EN_PROHIBITION.search(text):
        return "prohibition"
    if re.search(r"\b(?:shall|must)\s+not\b", text, re.IGNORECASE):
        return "prohibition"
    if re.search(r"\bmay\s+not\b", text, re.IGNORECASE):
        return "prohibition"
    if _EN_DEFINITION.search(text) and not (
        _EN_OBLIGATION.search(text) or _EN_PERMISSION.search(text)
    ):
        return "definition"
    if _EN_OBLIGATION.search(text):
        return "obligation"
    if _EN_PERMISSION.search(text):
        return "permission"
    if _EN_DEFINITION.search(text):
        return "definition"
    return None


def split_german_units(text: str) -> list[str]:
    text = text.strip()
    if not text:
        return []
    parts = _DE_SENT_SPLIT.split(text)
    return [p.strip() for p in parts if p.strip()]


def align_german_to_english_units(
    german_text: str,
    english_units: Sequence[str],
) -> list[str]:
    """Deterministic DE->EN unit alignment without reading Gold labels."""
    de_units = split_german_units(german_text)
    n_en = len(english_units)
    if n_en == 0:
        return []
    if not de_units:
        return [german_text.strip() or german_text] * n_en
    if len(de_units) == n_en:
        return de_units
    if len(de_units) == 1:
        return [de_units[0]] * n_en
    if n_en == 1:
        return [" ".join(de_units)]
    total = sum(max(len(u), 1) for u in de_units)
    targets = [max(len(u), 1) / total for u in english_units]
    assigned: list[str] = []
    cursor = 0
    acc = 0.0
    for i, share in enumerate(targets):
        acc += share
        if i == n_en - 1:
            chunk = de_units[cursor:]
        else:
            end = max(cursor + 1, int(round(acc * len(de_units))))
            end = min(end, len(de_units) - (n_en - i - 1))
            chunk = de_units[cursor:end]
            cursor = end
        assigned.append(" ".join(chunk) if chunk else de_units[min(cursor, len(de_units) - 1)])
    return assigned


def _is_list_fragment(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return True
    if _LIST_CONTINUATION.match(stripped) and len(stripped.split()) <= 12:
        return True
    if re.match(r"^\d+[\.\)]", stripped) and not english_marker_modality(stripped):
        return True
    return False


def merge_corenlp_sentence_groups(
    annotation: Mapping[str, Any],
    source_text: str,
) -> list[dict[str, Any]]:
    """Merge over-split CoreNLP sentences into clause-like units."""
    sentences = list(annotation["sentences"])
    if not sentences:
        return []
    groups: list[list[int]] = []
    current = [0]
    for index in range(1, len(sentences)):
        text = source_text[
            sentences[index]["tokens"][0]["characterOffsetBegin"] :
            sentences[index]["tokens"][-1]["characterOffsetEnd"]
        ]
        prev_text = source_text[
            sentences[current[-1]]["tokens"][0]["characterOffsetBegin"] :
            sentences[current[-1]]["tokens"][-1]["characterOffsetEnd"]
        ]
        if _is_list_fragment(text) or (
            not english_marker_modality(text)
            and english_marker_modality(prev_text)
            and len(text.split()) <= 20
            and not prev_text.rstrip().endswith((".", "!", "?"))
        ):
            current.append(index)
        else:
            groups.append(current)
            current = [index]
    groups.append(current)
    return [{"sentence_indexes": idxs, "primary_index": idxs[0]} for idxs in groups]


def split_group_by_coordinated_modality(
    source_text: str,
    annotation: Mapping[str, Any],
    group: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Optional split of one merged group when multiple modality markers coordinate."""
    sentences = annotation["sentences"]
    indexes = list(group["sentence_indexes"])
    start = sentences[indexes[0]]["tokens"][0]["characterOffsetBegin"]
    end = sentences[indexes[-1]]["tokens"][-1]["characterOffsetEnd"]
    text = source_text[start:end]
    markers = list(
        re.finditer(
            r"\b(?:shall\s+not|must\s+not|may\s+not|shall|must|may|means|is\s+defined\s+as)\b",
            text,
            re.IGNORECASE,
        )
    )
    if len(markers) < 2 or len(indexes) != 1:
        return [dict(group)]
    splits: list[int] = []
    for match in _COORD_MODALITY.finditer(text):
        left = text[: match.start()]
        right = text[match.end() :]
        if english_marker_modality(left) and english_marker_modality(right):
            splits.append(match.start())
    if not splits:
        return [dict(group)]
    pieces: list[dict[str, Any]] = []
    cursor = 0
    for cut in splits + [len(text)]:
        piece = text[cursor:cut].strip()
        if not piece:
            cursor = cut
            continue
        abs_start = start + cursor
        while abs_start < end and source_text[abs_start].isspace():
            abs_start += 1
        abs_end = start + cut
        while abs_end > abs_start and source_text[abs_end - 1].isspace():
            abs_end -= 1
        pieces.append(
            {
                "sentence_indexes": indexes,
                "primary_index": indexes[0],
                "clause_char_span": (abs_start, abs_end),
            }
        )
        cursor = cut
    return pieces or [dict(group)]


def plan_clause_units(
    annotation: Mapping[str, Any],
    source_text: str,
) -> list[dict[str, Any]]:
    groups = merge_corenlp_sentence_groups(annotation, source_text)
    planned: list[dict[str, Any]] = []
    for group in groups:
        planned.extend(split_group_by_coordinated_modality(source_text, annotation, group))
    return planned


def _plain_span(source_text: str, start: int, end: int) -> dict[str, Any]:
    if start < 0 or end <= start or end > len(source_text):
        raise Estg150B0DevelopmentError(f"invalid character span [{start}:{end}]")
    return {"text": source_text[start:end], "start": start, "end": end}


def _token_span(
    source_text: str,
    sentence: Mapping[str, Any],
    observation: Mapping[str, Any],
) -> dict[str, Any]:
    tokens = sentence["tokens"]
    begin = observation["begin"]
    end = observation["end"]
    start_offset = tokens[begin]["characterOffsetBegin"]
    end_offset = tokens[end - 1]["characterOffsetEnd"]
    return _plain_span(source_text, start_offset, end_offset)


def _supported_span(
    source_text: str,
    sentence: Mapping[str, Any],
    observation: Mapping[str, Any],
    *,
    span_id: str,
) -> dict[str, Any]:
    span = _token_span(source_text, sentence, observation)
    return {
        "id": span_id,
        **span,
        "normalized": " ".join(span["text"].casefold().split()),
    }


def _trim_actor_span(source_text: str, span: dict[str, Any]) -> dict[str, Any] | None:
    text = span["text"].strip()
    if not text:
        return None
    tokens = text.split()
    if len(tokens) == 1 and tokens[0].casefold() in _PRONOUN_ACTORS:
        return None
    if len(tokens) > _ACTOR_MAX_TOKENS:
        # Keep a trailing window by whitespace tokens, but re-slice source_text.
        parts = re.findall(r"\S+|\s+", span["text"])
        kept: list[str] = []
        word_count = 0
        for part in reversed(parts):
            kept.append(part)
            if not part.isspace():
                word_count += 1
            if word_count >= _ACTOR_MAX_TOKENS:
                break
        fragment = "".join(reversed(kept)).strip()
        if not fragment:
            return None
        rel = span["text"].rfind(fragment)
        if rel < 0:
            return None
        start = span["start"] + rel
        end = start + len(fragment)
        fragment = source_text[start:end]
        span = {
            "id": span["id"],
            "text": fragment,
            "start": start,
            "end": end,
            "normalized": " ".join(fragment.casefold().split()),
        }
    if re.fullmatch(r"[\d\.\)\-\u2014;,:]+", span["text"].strip()):
        return None
    lowered = span["text"].casefold()
    words = [w for w in re.findall(r"[a-zA-Z\u00c0-\u024f]+", lowered)]
    if not words:
        return None
    # Keep actors that look like legal entities / lexicon hits / title case heads.
    lexicon_hit = any(w in _ACTOR_SURFACES for w in words)
    titleish = any(tok[:1].isupper() for tok in span["text"].split() if tok[:1].isalpha())
    if not lexicon_hit and not titleish and len(words) > 4:
        return None
    if not lexicon_hit and words and words[0] in {"the", "a", "an", "this", "these", "those", "such"} and len(words) > 6:
        return None
    return span


def _dedupe_spans(spans: list[dict[str, Any]]) -> list[dict[str, Any]]:
    kept: list[dict[str, Any]] = []
    for span in sorted(spans, key=lambda s: (s["start"], -(s["end"] - s["start"]), s["text"])):
        overlapping = [
            k for k in kept if not (span["end"] <= k["start"] or span["start"] >= k["end"])
        ]
        if overlapping:
            longer = max(overlapping + [span], key=lambda s: (s["end"] - s["start"], -s["start"]))
            for k in overlapping:
                kept.remove(k)
            kept.append(longer)
            continue
        kept.append(span)
    kept.sort(key=lambda s: (s["start"], s["end"], s["text"]))
    return kept


def _restrict_observation_to_clause(
    observation: Mapping[str, Any],
    sentence: Mapping[str, Any],
    source_text: str,
    clause_start: int,
    clause_end: int,
) -> dict[str, Any] | None:
    span = _token_span(source_text, sentence, observation)
    if span["end"] <= clause_start or span["start"] >= clause_end:
        return None
    overlap = min(span["end"], clause_end) - max(span["start"], clause_start)
    if overlap <= 0:
        return None
    if overlap / max(span["end"] - span["start"], 1) < 0.5:
        return None
    return dict(observation)


def build_canonical_record_enhanced(
    *,
    sample_id: str,
    source_id: str,
    source_text: str,
    annotation: Mapping[str, Any],
    phrase_cases: Sequence[Mapping[str, Any]],
    clause_units: Sequence[Mapping[str, Any]],
    predictions: Sequence[ModalityPrediction],
) -> dict[str, Any]:
    try:
        validate_annotation(annotation, source_text)
    except CoreNLPContractError as exc:
        raise Estg150B0DevelopmentError(str(exc)) from exc
    sentences = annotation["sentences"]
    if len(predictions) != len(clause_units):
        raise Estg150B0DevelopmentError("one modality prediction is required per clause unit")
    cases_by_sentence: dict[int, Mapping[str, Any]] = {}
    for case in phrase_cases:
        index = case.get("sentence_index")
        if not isinstance(index, int) or isinstance(index, bool) or index in cases_by_sentence:
            raise Estg150B0DevelopmentError("phrase case indexes must be unique integers")
        cases_by_sentence[index] = case

    clauses: list[dict[str, Any]] = []
    for unit_index, (unit, prediction) in enumerate(
        zip(clause_units, predictions, strict=True)
    ):
        sentence_indexes = unit["sentence_indexes"]
        primary = unit["primary_index"]
        if "clause_char_span" in unit:
            clause_start, clause_end = unit["clause_char_span"]
        else:
            clause_start = sentences[sentence_indexes[0]]["tokens"][0]["characterOffsetBegin"]
            clause_end = sentences[sentence_indexes[-1]]["tokens"][-1]["characterOffsetEnd"]
        clause_span = _plain_span(source_text, clause_start, clause_end)
        clause_id = f"{sample_id}.c{unit_index + 1}"

        field_obs: dict[str, list[tuple[Mapping[str, Any], Mapping[str, Any]]]] = {
            "modality": [],
            "actor": [],
            "action": [],
            "condition": [],
            "constraint": [],
            "exception": [],
        }
        for sidx in sentence_indexes:
            fields = cases_by_sentence.get(sidx, {}).get("fields", {})
            sent = sentences[sidx]
            for field in field_obs:
                values = fields.get(field) or []
                if isinstance(values, Mapping):
                    values = [values]
                for obs in values:
                    if not isinstance(obs, Mapping):
                        continue
                    restricted = _restrict_observation_to_clause(
                        obs, sent, source_text, clause_start, clause_end
                    )
                    if restricted is not None:
                        field_obs[field].append((sent, restricted))

        modality_evidence = []
        for sent, obs in field_obs["modality"]:
            modality_evidence.append(_token_span(source_text, sent, obs))
        if not modality_evidence:
            modality_evidence = [dict(clause_span)]

        mapped: dict[str, list[dict[str, Any]]] = {}
        for singular, plural in (
            ("actor", "actors"),
            ("action", "actions"),
            ("condition", "conditions"),
            ("constraint", "constraints"),
            ("exception", "exceptions"),
        ):
            spans: list[dict[str, Any]] = []
            for rank, (sent, obs) in enumerate(field_obs[singular], start=1):
                span = _supported_span(
                    source_text,
                    sent,
                    obs,
                    span_id=f"{clause_id}.{singular}.{rank}",
                )
                if singular == "actor":
                    trimmed = _trim_actor_span(source_text, span)
                    if trimmed is None:
                        continue
                    span = trimmed
                if singular == "action" and len(span["text"].split()) > 40:
                    parts = re.findall(r"\S+|\s+", span["text"])
                    kept: list[str] = []
                    words = 0
                    for part in parts:
                        kept.append(part)
                        if not part.isspace():
                            words += 1
                        if words >= 12:
                            break
                    fragment = "".join(kept).rstrip()
                    end = span["start"] + len(fragment)
                    fragment = source_text[span["start"]:end]
                    span = {
                        "id": span["id"],
                        "text": fragment,
                        "start": span["start"],
                        "end": end,
                        "normalized": " ".join(fragment.casefold().split()),
                    }
                spans.append(span)
            mapped[plural] = _dedupe_spans(spans)
            remapped = []
            for rank, span in enumerate(mapped[plural], start=1):
                remapped.append(
                    {
                        "id": f"{clause_id}.{singular}.{rank}",
                        "text": span["text"],
                        "start": span["start"],
                        "end": span["end"],
                        "normalized": span["normalized"],
                    }
                )
            mapped[plural] = remapped

        actor_action_map = []
        if mapped["actors"] and mapped["actions"]:
            actor_id = mapped["actors"][0]["id"]
            for action in mapped["actions"]:
                actor_action_map.append(
                    {"actor_id": actor_id, "action_id": action["id"]}
                )

        clauses.append(
            {
                "clause_id": clause_id,
                "clause_span": clause_span,
                "modality": {
                    "label": prediction.label,
                    "evidence": modality_evidence[:1],
                },
                **mapped,
                "actor_action_map": actor_action_map,
                "order_relations": [],
            }
        )

    record = {
        "schema_version": SCHEMA_VERSION,
        "sample_id": sample_id,
        "source_id": source_id,
        "source_text": source_text,
        "clauses": clauses,
        "method": {"name": METHOD_ID, "schema_source": SCHEMA_SOURCE},
        "validation": {"schema_valid": True, "cross_field_valid": True, "errors": []},
    }
    report = validate_canonical(record)
    if not (report.schema_valid and report.cross_field_valid):
        raise Estg150B0DevelopmentError(
            "composed canonical record is invalid: " + "; ".join(report.errors)
        )
    return record


def _verify_runtime_identity(project_root: Path, runtime_home: Path) -> dict[str, Any]:
    config = load_object(project_root / "configs/sun_corenlp_runtime.json")
    identity = config["external_runtime_identity"]
    result: dict[str, Any] = {}
    for key in ("code_jar", "models_jar"):
        expected = identity[key]
        path = runtime_home / expected["name"]
        if not path.is_file():
            raise Estg150B0DevelopmentError(f"missing CoreNLP runtime JAR: {path}")
        actual = {"bytes": path.stat().st_size, "sha256": sha256_file(path)}
        if actual != {"bytes": expected["bytes"], "sha256": expected["sha256"]}:
            raise Estg150B0DevelopmentError(f"CoreNLP runtime identity mismatch: {path.name}")
        result[key] = {"name": path.name, **actual}
    return result


def run_corenlp_batch_enhanced(
    project_root: Path,
    source_records: Sequence[Mapping[str, Any]],
    *,
    runtime_home: Path,
    work_dir: Path,
) -> tuple[dict[str, dict[str, Any]], dict[str, list[dict[str, Any]]], dict[str, Any]]:
    root = Path(project_root).resolve()
    runtime_home = Path(runtime_home).resolve()
    runtime_identity = _verify_runtime_identity(root, runtime_home)
    probe = resolve_corenlp_runtime(root, home=runtime_home)
    if not probe.ready or not probe.java_executable:
        raise Estg150B0DevelopmentError(f"CoreNLP runtime unavailable: {probe.reasons}")
    javac = shutil.which("javac")
    if not javac:
        raise Estg150B0DevelopmentError("javac is required for the enhanced bridge")

    input_dir = work_dir / "corenlp-input"
    output_dir = work_dir / "corenlp-output"
    classes_dir = work_dir / "bridge-classes"
    input_dir.mkdir(parents=True)
    output_dir.mkdir()
    classes_dir.mkdir()
    input_paths: list[Path] = []
    source_by_id: dict[str, str] = {}
    for record in source_records:
        sample_id = record["sample_id"]
        source_text = record["approved_text_en"]
        path = input_dir / f"{sample_id}.txt"
        path.write_text(source_text, encoding="utf-8", newline="\n")
        input_paths.append(path)
        source_by_id[sample_id] = source_text
    file_list = work_dir / "corenlp-filelist.txt"
    file_list.write_text(
        "\n".join(str(path.resolve()) for path in input_paths) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    runtime_contract = load_object(root / "configs/sun_corenlp_runtime.json")["runtime"]
    classpath = os.pathsep.join(probe.classpath_entries)
    corenlp_command = [
        probe.java_executable,
        f"-Xmx{runtime_contract['heap_megabytes']}m",
        "-cp",
        classpath,
        "edu.stanford.nlp.pipeline.StanfordCoreNLP",
        "-annotators",
        ",".join(runtime_contract["annotators"]),
        "-outputFormat",
        "json",
        "-filelist",
        str(file_list.resolve()),
        "-outputDirectory",
        str(output_dir.resolve()),
        "-replaceExtension",
    ]
    started = time.perf_counter()
    _run(corenlp_command, cwd=root, timeout=max(1800, 12 * len(source_records)))
    corenlp_seconds = time.perf_counter() - started

    annotations: dict[str, dict[str, Any]] = {}
    sentence_refs: list[tuple[str, int]] = []
    tree_lines: list[str] = []
    for record in source_records:
        sample_id = record["sample_id"]
        candidates = list(output_dir.rglob(f"{sample_id}.json"))
        if len(candidates) != 1:
            raise Estg150B0DevelopmentError(
                f"expected one CoreNLP JSON for {sample_id}, found {len(candidates)}"
            )
        annotation = load_object(candidates[0])
        try:
            validate_annotation(annotation, source_by_id[sample_id])
        except CoreNLPContractError as exc:
            raise Estg150B0DevelopmentError(f"{sample_id}: {exc}") from exc
        annotations[sample_id] = annotation
        for local_index, sentence in enumerate(annotation["sentences"]):
            sentence_refs.append((sample_id, local_index))
            tree_lines.append(" ".join(sentence["parse"].split()))

    registry = load_object(root / PATTERNS_REL)
    plan_path = work_dir / "rule-plan.tsv"
    pattern_count = _write_rule_plan(registry, plan_path)
    bridge_path = root / BRIDGE_REL
    compile_command = [
        javac, "--release", "8", "-encoding", "UTF-8",
        "-cp", classpath, "-d", str(classes_dir), str(bridge_path),
    ]
    _run(compile_command, cwd=root, timeout=180)
    tree_path = work_dir / "trees.txt"
    tree_path.write_text("\n".join(tree_lines) + "\n", encoding="utf-8", newline="\n")
    bridge_classpath = os.pathsep.join((str(classes_dir), classpath))
    bridge_started = time.perf_counter()
    bridge = _run(
        [
            probe.java_executable, "-cp", bridge_classpath, BRIDGE_CLASS,
            str(plan_path), str(tree_path),
        ],
        cwd=root,
        timeout=600,
    )
    bridge_seconds = time.perf_counter() - bridge_started
    global_cases, bridge_summary = parse_bridge_output_multi(bridge.stdout)
    if bridge_summary["pattern_count"] != pattern_count:
        raise Estg150B0DevelopmentError("bridge pattern count mismatch")
    if bridge_summary["tree_count"] != len(sentence_refs) or len(global_cases) != len(sentence_refs):
        raise Estg150B0DevelopmentError("bridge sentence coverage mismatch")
    cases_by_id: dict[str, list[dict[str, Any]]] = {
        record["sample_id"]: [] for record in source_records
    }
    for global_case, (sample_id, local_index) in zip(global_cases, sentence_refs, strict=True):
        cases_by_id[sample_id].append(
            {"sentence_index": local_index, "fields": global_case["fields"]}
        )
    return annotations, cases_by_id, {
        "runtime_identity": runtime_identity,
        "corenlp_seconds": corenlp_seconds,
        "bridge_seconds": bridge_seconds,
        "sentence_count": len(sentence_refs),
        "pattern_count": pattern_count,
        "match_count": bridge_summary["match_count"],
        "surgery_count": bridge_summary["surgery_count"],
        "terminal_tree_removal_count": bridge_summary["terminal_tree_removal_count"],
        "bridge_class": BRIDGE_CLASS,
        "patterns_path": PATTERNS_REL,
    }


def _predict_in_batches(
    classifier: LockedBertTextCNNInference,
    texts: Sequence[str],
    *,
    batch_size: int = 16,
) -> list[ModalityPrediction]:
    predictions: list[ModalityPrediction] = []
    for start in range(0, len(texts), batch_size):
        predictions.extend(classifier.predict(texts[start : start + batch_size]))
    return predictions


def run_b0_batch_enhanced(
    project_root: Path,
    source_records: Sequence[Mapping[str, Any]],
    *,
    runtime_home: Path,
    work_dir: Path,
    device: str = "cpu",
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    root = Path(project_root).resolve()
    s26_config = load_s26_config(root / "configs/models/sun_b0_s26.json")
    annotations, cases_by_id, runtime = run_corenlp_batch_enhanced(
        root, source_records, runtime_home=runtime_home, work_dir=work_dir
    )
    classifier_started = time.perf_counter()
    try:
        classifier = LockedBertTextCNNInference.load(root, s26_config, device=device)
    except SunB0CompositionError as exc:
        raise Estg150B0DevelopmentError(str(exc)) from exc

    planned: list[tuple[Mapping[str, Any], list[dict[str, Any]], list[str], list[str]]] = []
    all_de_texts: list[str] = []
    for record in source_records:
        sample_id = record["sample_id"]
        annotation = annotations[sample_id]
        source_text = record["approved_text_en"]
        clause_units = plan_clause_units(annotation, source_text)
        en_texts = []
        for unit in clause_units:
            if "clause_char_span" in unit:
                s, e = unit["clause_char_span"]
            else:
                idxs = unit["sentence_indexes"]
                s = annotation["sentences"][idxs[0]]["tokens"][0]["characterOffsetBegin"]
                e = annotation["sentences"][idxs[-1]]["tokens"][-1]["characterOffsetEnd"]
            en_texts.append(source_text[s:e])
        de_units = align_german_to_english_units(record["raw_text_de"], en_texts)
        planned.append((record, clause_units, en_texts, de_units))
        all_de_texts.extend(de_units)

    de_predictions = _predict_in_batches(classifier, all_de_texts)
    classifier_seconds = time.perf_counter() - classifier_started

    compose_started = time.perf_counter()
    canonical_records: list[dict[str, Any]] = []
    label_counts: dict[str, int] = {}
    confidence_sum = 0.0
    pred_cursor = 0
    modality_route_counts = {
        "aligned_classifier": 0,
        "prohibition_override": 0,
        "misaligned_en_marker": 0,
        "misaligned_classifier_fallback": 0,
    }
    for record, clause_units, en_texts, de_units in planned:
        sample_id = record["sample_id"]
        unit_predictions: list[ModalityPrediction] = []
        de_count = len(split_german_units(record["raw_text_de"])) or 1
        en_count = len(en_texts)
        for en_text, de_text in zip(en_texts, de_units, strict=True):
            base = de_predictions[pred_cursor]
            pred_cursor += 1
            en_label = english_marker_modality(en_text)
            if en_label is not None:
                # English approved text is the phrase/canonical surface; public
                # markers are high-precision cues for deontic force on that surface.
                conf = max(base.confidence, 0.6 if en_label == "prohibition" else 0.55)
                final = ModalityPrediction(en_label, conf)
                if de_count == en_count and en_label == base.label:
                    modality_route_counts["aligned_classifier"] += 1
                elif en_label == "prohibition" and base.label != "prohibition":
                    modality_route_counts["prohibition_override"] += 1
                else:
                    modality_route_counts["misaligned_en_marker"] += 1
            elif de_count == en_count:
                final = base
                modality_route_counts["aligned_classifier"] += 1
            else:
                final = base
                modality_route_counts["misaligned_classifier_fallback"] += 1
            unit_predictions.append(final)
            label_counts[final.label] = label_counts.get(final.label, 0) + 1
            confidence_sum += final.confidence
        canonical = build_canonical_record_enhanced(
            sample_id=sample_id,
            source_id=f"estg_legacy_{record['legacy_record_id']}",
            source_text=record["approved_text_en"],
            annotation=annotations[sample_id],
            phrase_cases=cases_by_id[sample_id],
            clause_units=clause_units,
            predictions=unit_predictions,
        )
        canonical_records.append(canonical)
    if pred_cursor != len(de_predictions):
        raise Estg150B0DevelopmentError("classifier prediction cursor mismatch")
    compose_seconds = time.perf_counter() - compose_started
    total_seconds = (
        runtime["corenlp_seconds"]
        + runtime["bridge_seconds"]
        + classifier_seconds
        + compose_seconds
    )
    per_record_latency_ms = 1000.0 * total_seconds / max(len(canonical_records), 1)
    attempts = [
        {
            "sample_id": record["sample_id"],
            "request_status": "ok",
            "record": record,
            "error_category": None,
            "runtime": {
                "llm_call_performed": False,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "estimated_cost_usd": 0.0,
                "latency_ms": per_record_latency_ms,
            },
        }
        for record in canonical_records
    ]
    runtime.update(
        {
            "classifier_seconds": classifier_seconds,
            "compose_seconds": compose_seconds,
            "total_seconds": total_seconds,
            "device": device,
            "record_count": len(canonical_records),
            "predicted_clause_count": sum(len(r["clauses"]) for r in canonical_records),
            "classifier_label_counts_by_clause": dict(sorted(label_counts.items())),
            "classifier_mean_confidence": confidence_sum / max(sum(label_counts.values()), 1),
            "modality_route_counts": modality_route_counts,
            "method_id": METHOD_ID,
            "method_variant": METHOD_VARIANT,
        }
    )
    return attempts, runtime


def sun_table8_any_overlap_diagnostic(
    gold_records: Sequence[Mapping[str, Any]],
    attempts: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Read-only diagnostic: any non-empty same-type span intersection is TP."""
    from bpc_hybrid.stage2_evaluation import _char_iou
    from bpc_hybrid.stage2_evaluation_v3 import CLAUSE_MINIMUM_IOU, clause_iou_pairs

    fields = ("actor", "action", "condition", "constraint", "exception")
    plural = {
        "actor": "actors",
        "action": "actions",
        "condition": "conditions",
        "constraint": "constraints",
        "exception": "exceptions",
    }
    counts = {field: {"tp": 0, "fp": 0, "fn": 0, "gold": 0, "pred": 0} for field in fields}
    gold_by_id = {row["sample_id"]: row for row in gold_records}
    for attempt in attempts:
        sample_id = attempt["sample_id"]
        gold = gold_by_id[sample_id]
        pred = attempt["record"]
        pairs, _, extra_pred, _ = clause_iou_pairs(
            gold.get("clauses") or [],
            pred.get("clauses") or [],
            minimum_iou=CLAUSE_MINIMUM_IOU,
        )
        for g_idx, p_idx in pairs:
            g_clause = gold["clauses"][g_idx]
            p_clause = pred["clauses"][p_idx]
            for field in fields:
                g_spans = list(g_clause.get(plural[field]) or [])
                p_spans = list(p_clause.get(plural[field]) or [])
                counts[field]["gold"] += len(g_spans)
                counts[field]["pred"] += len(p_spans)
                used_p: set[int] = set()
                for g_span in g_spans:
                    hit = None
                    for pi, p_span in enumerate(p_spans):
                        if pi in used_p:
                            continue
                        if _char_iou(g_span, p_span) > 0.0:
                            hit = pi
                            break
                    if hit is not None:
                        counts[field]["tp"] += 1
                        used_p.add(hit)
                    else:
                        counts[field]["fn"] += 1
                counts[field]["fp"] += len(p_spans) - len(used_p)
        for p_idx in extra_pred:
            p_clause = pred["clauses"][p_idx]
            for field in fields:
                p_spans = list(p_clause.get(plural[field]) or [])
                counts[field]["pred"] += len(p_spans)
                counts[field]["fp"] += len(p_spans)
        matched_gold = {g for g, _ in pairs}
        for g_idx, g_clause in enumerate(gold.get("clauses") or []):
            if g_idx in matched_gold:
                continue
            for field in fields:
                g_spans = list(g_clause.get(plural[field]) or [])
                counts[field]["gold"] += len(g_spans)
                counts[field]["fn"] += len(g_spans)

    def prf(tp: int, fp: int, fn: int) -> dict[str, float | int]:
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        return {"precision": precision, "recall": recall, "f1": f1, "tp": tp, "fp": fp, "fn": fn}

    per_field = {
        field: prf(v["tp"], v["fp"], v["fn"]) | {"gold": v["gold"], "pred": v["pred"]}
        for field, v in counts.items()
    }
    total_tp = sum(v["tp"] for v in counts.values())
    total_fp = sum(v["fp"] for v in counts.values())
    total_fn = sum(v["fn"] for v in counts.values())
    return {
        "diagnostic_id": "sun_table8_any_overlap_diagnostic",
        "claim_scope": "development_diagnostic_only",
        "is_formal_metric": False,
        "match_rule": "same_field_any_nonempty_character_span_intersection",
        "per_field": per_field,
        "overall": prf(total_tp, total_fp, total_fn),
    }
