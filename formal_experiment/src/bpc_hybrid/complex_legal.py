"""Deterministic S2.11 GDPR source extraction and human-Gold validation.

This module never reads model predictions or evaluation results.  It parses the
official EUR-Lex/Cellar Formex XML, defines paragraph-level source units for
Articles 5--50, and applies the preregistered coverage-first seeded selection.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence
from xml.etree import ElementTree

from bpc_hybrid.stage2_canonical import validate_canonical


DATASET_SCHEMA = "complex_legal_input@1.0.0"
REVIEW_SCHEMA = "complex_legal_human_gold_review@1.0.0"
DATASET_ID = "gdpr_2016_679_articles_5_50_seeded50_v1"
SOURCE_ID = "celex_32016R0679_oj_en"
SELECTION_SEED = "s211-gdpr-articles-5-50-coverage-seed-20260717-v1"
ARTICLE_MIN = 5
ARTICLE_MAX = 50
TARGET_COUNT = 50
DECISION_FIELDS = (
    "source_verified",
    "clause_segmentation",
    "modality",
    "actors",
    "actions",
    "conditions",
    "constraints",
    "exceptions",
    "actor_action_map",
    "order_relations",
)
FINAL_DECISIONS = {"accepted", "edited", "rejected"}


class ComplexLegalContractError(ValueError):
    """Raised when the S2.11 source, membership, or review contract fails."""


@dataclass(frozen=True)
class SourceUnit:
    article: int
    paragraph: int
    article_title: str
    source_locator: str
    source_text: str
    source_text_sha256: str
    sample_id: str
    selection_rank_sha256: str


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalize_legal_text(value: str) -> str:
    """Apply the frozen source-text normalization used for membership hashes."""

    normalized = unicodedata.normalize("NFKC", value)
    normalized = normalized.replace("\u00ad", "").replace("\u00a0", " ")
    return re.sub(r"\s+", " ", normalized).strip()


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _text_without(root: ElementTree.Element, excluded: set[str]) -> str:
    parts: list[str] = []

    def visit(node: ElementTree.Element) -> None:
        if node.text:
            parts.append(node.text)
        for child in node:
            if _local_name(child.tag) not in excluded:
                visit(child)
            if child.tail:
                parts.append(child.tail)

    visit(root)
    return normalize_legal_text(" ".join(parts))


def _paragraph_number(article: int, paragraph: ElementTree.Element) -> int:
    identifier = paragraph.get("IDENTIFIER", "")
    match = re.fullmatch(rf"{article:03d}\.([0-9]{{3}})", identifier)
    if not match:
        raise ComplexLegalContractError(
            f"unexpected Formex paragraph identifier in Article {article}: {identifier!r}"
        )
    return int(match.group(1))


def parse_article_units(xml_path: Path) -> list[SourceUnit]:
    raw = Path(xml_path).read_bytes()
    upper = raw.upper()
    if b"<!DOCTYPE" in upper or b"<!ENTITY" in upper:
        raise ComplexLegalContractError("Formex XML with DTD/entity declarations is forbidden")
    try:
        root = ElementTree.fromstring(raw)
    except ElementTree.ParseError as exc:
        raise ComplexLegalContractError(f"invalid Formex XML: {xml_path}") from exc

    language = root.findtext("./BIB.INSTANCE/LG.DOC")
    number = root.findtext("./BIB.INSTANCE/NO.DOC/NO.CURRENT")
    year = root.findtext("./BIB.INSTANCE/NO.DOC/YEAR")
    community = root.findtext("./BIB.INSTANCE/NO.DOC/COM")
    if (language, number, year, community) != ("EN", "679", "2016", "EU"):
        raise ComplexLegalContractError("Formex identity is not English Regulation (EU) 2016/679")

    articles: dict[int, ElementTree.Element] = {}
    for article in root.findall(".//ARTICLE"):
        identifier = article.get("IDENTIFIER", "")
        if not re.fullmatch(r"[0-9]{3}", identifier):
            raise ComplexLegalContractError(f"invalid article identifier: {identifier!r}")
        number_value = int(identifier)
        if number_value in articles:
            raise ComplexLegalContractError(f"duplicate article identifier: {identifier}")
        articles[number_value] = article
    expected_articles = set(range(1, 100))
    if set(articles) != expected_articles:
        raise ComplexLegalContractError("official Formex source must contain Articles 1--99 exactly once")

    units: list[SourceUnit] = []
    for article_number in range(ARTICLE_MIN, ARTICLE_MAX + 1):
        article = articles[article_number]
        article_title = normalize_legal_text(article.findtext("./STI.ART") or "")
        paragraphs = article.findall("./PARAG")
        if paragraphs:
            candidates = [
                (
                    _paragraph_number(article_number, paragraph),
                    f"ARTICLE[@IDENTIFIER='{article_number:03d}']/PARAG[@IDENTIFIER='{paragraph.get('IDENTIFIER')}']",
                    _text_without(paragraph, {"NO.PARAG", "NOTE"}),
                )
                for paragraph in paragraphs
            ]
        else:
            alineas = article.findall("./ALINEA")
            if len(alineas) != 1:
                raise ComplexLegalContractError(
                    f"Article {article_number} must have paragraphs or one direct ALINEA"
                )
            candidates = [
                (
                    0,
                    f"ARTICLE[@IDENTIFIER='{article_number:03d}']/ALINEA[1]",
                    _text_without(alineas[0], {"NOTE"}),
                )
            ]

        for paragraph_number, locator, text in candidates:
            if not text:
                raise ComplexLegalContractError(f"empty source unit: {locator}")
            text_hash = sha256_bytes(text.encode("utf-8"))
            sample_id = (
                f"gdpr_2016_679_art{article_number:03d}_par{paragraph_number:03d}"
            )
            rank = sha256_bytes(
                f"{SELECTION_SEED}\n{locator}\n{text_hash}".encode("utf-8")
            )
            units.append(
                SourceUnit(
                    article=article_number,
                    paragraph=paragraph_number,
                    article_title=article_title,
                    source_locator=locator,
                    source_text=text,
                    source_text_sha256=text_hash,
                    sample_id=sample_id,
                    selection_rank_sha256=rank,
                )
            )
    if len({unit.sample_id for unit in units}) != len(units):
        raise ComplexLegalContractError("source-unit sample IDs are not unique")
    return units


def select_coverage_seeded50(units: Sequence[SourceUnit]) -> list[dict[str, Any]]:
    by_article: dict[int, list[SourceUnit]] = {
        article: [] for article in range(ARTICLE_MIN, ARTICLE_MAX + 1)
    }
    for unit in units:
        if unit.article not in by_article:
            raise ComplexLegalContractError("selection received an out-of-scope article")
        by_article[unit.article].append(unit)
    if any(not values for values in by_article.values()):
        raise ComplexLegalContractError("every Article 5--50 requires at least one source unit")

    coverage = {
        min(values, key=lambda item: (item.selection_rank_sha256, item.sample_id)).sample_id
        for values in by_article.values()
    }
    remaining = sorted(
        (unit for unit in units if unit.sample_id not in coverage),
        key=lambda item: (item.selection_rank_sha256, item.sample_id),
    )
    supplement_count = TARGET_COUNT - len(coverage)
    if supplement_count < 0 or len(remaining) < supplement_count:
        raise ComplexLegalContractError("coverage selection cannot satisfy target count")
    supplement = {unit.sample_id for unit in remaining[:supplement_count]}
    chosen = [unit for unit in units if unit.sample_id in coverage | supplement]
    chosen.sort(key=lambda item: (item.article, item.paragraph))
    if len(chosen) != TARGET_COUNT:
        raise ComplexLegalContractError("coverage-first selection did not produce 50 samples")
    if {unit.article for unit in chosen} != set(range(ARTICLE_MIN, ARTICLE_MAX + 1)):
        raise ComplexLegalContractError("selected membership does not cover Articles 5--50")
    if len({unit.source_text_sha256 for unit in chosen}) != TARGET_COUNT:
        raise ComplexLegalContractError("selected membership contains duplicate normalized text")

    records: list[dict[str, Any]] = []
    for unit in chosen:
        records.append(
            {
                "schema_version": DATASET_SCHEMA,
                "dataset_id": DATASET_ID,
                "sample_id": unit.sample_id,
                "source_id": SOURCE_ID,
                "source_locator": unit.source_locator,
                "article": unit.article,
                "paragraph": unit.paragraph,
                "article_title": unit.article_title,
                "source_text": unit.source_text,
                "source_text_sha256": unit.source_text_sha256,
                "source_language": "en",
                "analysis_language": "en",
                "translation_status": "original",
                "selection_role": (
                    "article_coverage" if unit.sample_id in coverage else "coverage_supplement"
                ),
                "selection_rank_sha256": unit.selection_rank_sha256,
                "gold_status": "pending_human_annotation",
            }
        )
    return records


def membership_payload(records: Sequence[Mapping[str, Any]]) -> str:
    return "".join(
        f"{record['sample_id']}\t{record['source_text_sha256']}\t{record['source_locator']}\n"
        for record in records
    )


def membership_sha256(records: Sequence[Mapping[str, Any]]) -> str:
    return sha256_bytes(membership_payload(records).encode("utf-8"))


def build_blank_review(records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    digest = membership_sha256(records)
    return {
        "schema_version": REVIEW_SCHEMA,
        "dataset_id": DATASET_ID,
        "membership_sha256": digest,
        "status": "template_pending_human_annotation",
        "records": [
            {
                "sample_id": record["sample_id"],
                "source_locator": record["source_locator"],
                "source_text": record["source_text"],
                "source_text_sha256": record["source_text_sha256"],
                "review_state": "needs_review",
                "record_decision": "unreviewed",
                "canonical_gold": None,
                "decisions": {field: "unreviewed" for field in DECISION_FIELDS},
                "reviewer": None,
                "reviewed_at": None,
                "notes": None,
            }
            for record in records
        ],
    }


def _load_schema(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ComplexLegalContractError(f"invalid review schema: {path}") from exc
    if not isinstance(value, dict):
        raise ComplexLegalContractError("review schema root must be an object")
    return value


def _validate_review_schema(review: Mapping[str, Any], schema_path: Path) -> list[str]:
    schema = _load_schema(schema_path)
    try:
        import jsonschema
    except ImportError:
        required = {"schema_version", "dataset_id", "membership_sha256", "status", "records"}
        return [] if set(review) == required else ["minimal review structure failed"]
    validator = jsonschema.Draft202012Validator(schema)
    return [
        f"{'.'.join(str(part) for part in error.path) or '<root>'}: {error.message}"
        for error in sorted(validator.iter_errors(dict(review)), key=lambda item: list(item.path))
    ]


def _canonical_gold_errors(record: Mapping[str, Any], source: Mapping[str, Any]) -> list[str]:
    gold = record.get("canonical_gold")
    if not isinstance(gold, Mapping):
        return ["canonical_gold must be an object for canonical_rule_present"]
    envelope = {
        "schema_version": "1.0.0",
        "sample_id": source["sample_id"],
        "source_id": SOURCE_ID,
        "source_text": source["source_text"],
        "clauses": copy.deepcopy(gold.get("clauses")),
        "method": {
            "name": "sun_rule_only",
            "schema_source": "stage2_prediction.schema.json@1.0.0",
        },
        "validation": {"schema_valid": False, "cross_field_valid": False, "errors": []},
    }
    if "unsupported_or_ambiguous" in gold:
        envelope["unsupported_or_ambiguous"] = copy.deepcopy(
            gold["unsupported_or_ambiguous"]
        )
    report = validate_canonical(envelope)
    return report.errors


def validate_human_gold_review(
    review: Mapping[str, Any],
    dataset: Sequence[Mapping[str, Any]],
    schema_path: Path,
) -> dict[str, Any]:
    errors = _validate_review_schema(review, schema_path)
    dataset_by_id = {record.get("sample_id"): record for record in dataset}
    review_records = review.get("records", [])
    if len(dataset_by_id) != TARGET_COUNT or len(review_records) != TARGET_COUNT:
        errors.append("dataset and review must each contain exactly 50 unique records")
    if review.get("membership_sha256") != membership_sha256(dataset):
        errors.append("review membership hash does not match frozen dataset")

    seen: set[str] = set()
    reviewed = 0
    adjudicated = 0
    canonical_present = 0
    for index, record in enumerate(review_records):
        sample_id = record.get("sample_id")
        if sample_id in seen:
            errors.append(f"records[{index}] duplicate sample_id: {sample_id!r}")
            continue
        seen.add(sample_id)
        source = dataset_by_id.get(sample_id)
        if source is None:
            errors.append(f"records[{index}] sample_id is outside frozen membership")
            continue
        for field in ("source_locator", "source_text", "source_text_sha256"):
            if record.get(field) != source.get(field):
                errors.append(f"records[{index}].{field} differs from frozen input")

        state = record.get("review_state")
        decision = record.get("record_decision")
        decisions = record.get("decisions", {})
        if state == "needs_review":
            if (
                decision != "unreviewed"
                or record.get("canonical_gold") is not None
                or any(decisions.get(field) != "unreviewed" for field in DECISION_FIELDS)
                or record.get("reviewer") is not None
                or record.get("reviewed_at") is not None
            ):
                errors.append(f"records[{index}] needs_review record is not blank")
            continue

        if state in {"reviewed", "adjudicated"}:
            reviewed += 1
        if state == "adjudicated":
            adjudicated += 1
        if decisions.get("source_verified") != "accepted":
            errors.append(f"records[{index}] reviewed source must be explicitly accepted")
        allowed = FINAL_DECISIONS | ({"needs_adjudication"} if state == "reviewed" else set())
        if any(decisions.get(field) not in allowed for field in DECISION_FIELDS):
            errors.append(f"records[{index}] has unresolved field decisions")
        if decision == "canonical_rule_present":
            canonical_present += 1
            for error in _canonical_gold_errors(record, source):
                errors.append(f"records[{index}].canonical_gold: {error}")
        elif decision in {"no_canonical_rule", "source_error"}:
            if record.get("canonical_gold") is not None:
                errors.append(f"records[{index}] non-rule decision requires canonical_gold=null")
        else:
            errors.append(f"records[{index}] reviewed record_decision is unresolved")
        if not isinstance(record.get("reviewer"), str) or not record.get("reviewer"):
            errors.append(f"records[{index}] reviewed record requires reviewer")
        if not isinstance(record.get("reviewed_at"), str) or not record.get("reviewed_at"):
            errors.append(f"records[{index}] reviewed record requires reviewed_at")

    status = review.get("status")
    freeze_ready = (
        not errors
        and status == "human_adjudicated_frozen"
        and adjudicated == TARGET_COUNT
    )
    if status == "human_adjudicated_frozen" and not freeze_ready:
        errors.append("human_adjudicated_frozen requires 50/50 valid adjudicated records")
        freeze_ready = False
    return {
        "format_valid": not errors,
        "input_ready": not errors and len(review_records) == TARGET_COUNT,
        "freeze_ready": freeze_ready,
        "reviewed": reviewed,
        "adjudicated": adjudicated,
        "canonical_rule_present": canonical_present,
        "errors": errors,
    }
