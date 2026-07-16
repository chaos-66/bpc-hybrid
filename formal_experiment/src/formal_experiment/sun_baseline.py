"""Audit the optional imported source against exact Sun Stage 2 requirements."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from formal_experiment.paths import SUN_PROGRAM_DIR


IMPLEMENTATION_SUFFIXES = {
    ".cfg",
    ".config",
    ".java",
    ".json",
    ".md",
    ".py",
    ".txt",
    ".xml",
    ".yaml",
    ".yml",
}

EXCLUDED_DIR_NAMES = {
    ".git",
    "__pycache__",
    "caches",
    "models",
    "performance",
    "regulations",
    "results",
}

FIELDS = ("modality", "actor", "action", "condition", "constraint", "exception")


@dataclass(frozen=True)
class BaselineIndicator:
    id: str
    status: str
    required_for_exact_stage2: bool
    description: str
    evidence_files: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _rel(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def _iter_candidate_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    files: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in EXCLUDED_DIR_NAMES for part in path.parts):
            continue
        if path.suffix.lower() in IMPLEMENTATION_SUFFIXES:
            files.append(path)
    return sorted(files)


def _read_text(path: Path) -> str:
    try:
        if path.stat().st_size > 2_000_000:
            return ""
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def _files_containing(
    root: Path,
    terms: tuple[str, ...],
    *,
    require_all: bool,
) -> list[str]:
    found: list[str] = []
    lowered_terms = tuple(term.lower() for term in terms)
    for path in _iter_candidate_files(root):
        text = _read_text(path).lower()
        if not text:
            continue
        matches = all(term in text for term in lowered_terms) if require_all else any(
            term in text for term in lowered_terms
        )
        if matches:
            found.append(_rel(path, root))
    return found


def _existing_files(root: Path, relative_paths: tuple[str, ...]) -> list[str]:
    return [rel for rel in relative_paths if (root / rel).exists()]


def _count_files(root: Path, pattern: str) -> int:
    if not root.exists():
        return 0
    return sum(1 for path in root.rglob(pattern) if path.is_file())


def audit_sun_baseline(root: Path = SUN_PROGRAM_DIR) -> dict[str, Any]:
    """Return a conservative audit of exact Sun Stage 2 availability.

    The optional exact-source reference is expected at
    ``references/sun_2024_original``. The separately named Winter 2020
    reference must never satisfy this audit.
    It is never imported by the formal experiment runtime.
    """

    model_root = root / "model_check"
    if (root / "lib/main.py").exists():
        model_root = root

    indicators: list[BaselineIndicator] = []

    model_check_files = _existing_files(
        model_root,
        (
            "lib/main.py",
            "lib/classes/Document_Collection.py",
            "lib/classes/Sentence.py",
            "lib/classes/Clause.py",
            "lib/classes/Pair.py",
            "lib/classes/SimilarityComputer.py",
        ),
    )
    indicators.append(
        BaselineIndicator(
            id="model_check_pipeline",
            status="present" if len(model_check_files) >= 5 else "missing",
            required_for_exact_stage2=False,
            description=(
                "The reference contains a spaCy-based GDPR/BPMN textual checking "
                "pipeline. It is closer to Winter-style textual matching than to "
                "Sun's BERT plus Tregex Stage 2 extractor."
            ),
            evidence_files=[f"model_check/{path}" for path in model_check_files],
        )
    )

    input_files = _existing_files(
        model_root,
        (
            "input/files/signalwords.txt",
            "input/files/sequencemarkers.txt",
            "input/files/stopwords.txt",
            "input/files/gdpr.config",
        ),
    )
    indicators.append(
        BaselineIndicator(
            id="marker_and_config_files",
            status="present" if len(input_files) >= 3 else "missing",
            required_for_exact_stage2=False,
            description="The reference contains marker/config files used by model_check.",
            evidence_files=[f"model_check/{path}" for path in input_files],
        )
    )

    bpmn_root = model_root / "input/models/gdpr"
    article_root = model_root / "input/regulations/gdpr"
    bpmn_count = _count_files(bpmn_root, "*.bpmn")
    article_count = _count_files(article_root, "*.txt")
    indicators.append(
        BaselineIndicator(
            id="gdpr_bpmn_assets",
            status="present" if bpmn_count and article_count else "missing",
            required_for_exact_stage2=False,
            description=(
                f"The reference contains {bpmn_count} BPMN files and "
                f"{article_count} GDPR article files."
            ),
            evidence_files=(
                ["model_check/input/models/gdpr", "model_check/input/regulations/gdpr"]
                if bpmn_count and article_count
                else []
            ),
        )
    )

    winter_style_files = _files_containing(
        model_root,
        ("fitness", "obligation costs", "resource costs", "so costs"),
        require_all=True,
    )
    indicators.append(
        BaselineIndicator(
            id="winter_style_textual_checking_signatures",
            status="present" if winter_style_files else "missing",
            required_for_exact_stage2=False,
            description=(
                "The reference writes fitness and cost columns associated with "
                "textual compliance matching, not Sun's six-concept extraction."
            ),
            evidence_files=[f"model_check/{path}" for path in winter_style_files],
        )
    )

    bert_files = _files_containing(
        model_root, ("bert", "transformers"), require_all=False
    )
    indicators.append(
        BaselineIndicator(
            id="bert_modality_classifier",
            status="present" if bert_files else "missing",
            required_for_exact_stage2=True,
            description=(
                "Sun Stage 2 uses a legal-domain BERT model for statement-level "
                "modality classification."
            ),
            evidence_files=[f"model_check/{path}" for path in bert_files],
        )
    )

    tregex_files = _files_containing(
        model_root,
        ("tregex", "tsurgeon", "edu.stanford", "treepattern"),
        require_all=False,
    )
    java_files = [
        _rel(path, model_root) for path in model_root.rglob("*.java")
    ] if model_root.exists() else []
    tregex_evidence = sorted(set(tregex_files + java_files))
    indicators.append(
        BaselineIndicator(
            id="tregex_tsurgeon_java_rules",
            status="present" if tregex_evidence else "missing",
            required_for_exact_stage2=True,
            description=(
                "Sun phrase-level extraction is reported as Tregex patterns, "
                "Tsurgeon operations, and Java implementation."
            ),
            evidence_files=[f"model_check/{path}" for path in tregex_evidence],
        )
    )

    six_field_files = _files_containing(model_root, FIELDS, require_all=True)
    indicators.append(
        BaselineIndicator(
            id="six_concept_stage2_extractor",
            status="present" if six_field_files else "missing",
            required_for_exact_stage2=True,
            description=(
                "Exact Stage 2 should explicitly produce modality, actor, action, "
                "condition, constraint, and exception fields."
            ),
            evidence_files=[f"model_check/{path}" for path in six_field_files],
        )
    )

    required_missing = [
        item.id
        for item in indicators
        if item.required_for_exact_stage2 and item.status != "present"
    ]

    return {
        "sun_program_dir": str(root),
        "reference_available": root.exists(),
        "exact_stage2_locked": not required_missing,
        "status": (
            "ready_exact_sun_stage2"
            if not required_missing
            else "blocked_missing_exact_sun_stage2"
        ),
        "required_missing": required_missing,
        "indicators": [item.to_dict() for item in indicators],
        "interpretation": (
            "The optional model_check reference resembles the Winter textual "
            "baseline style and is not sufficient as exact Sun Stage 2. The formal "
            "runtime does not import it."
        ),
    }


def print_human(audit: dict[str, Any]) -> None:
    print("Sun baseline audit")
    print("=" * 32)
    print(f"Reference path: {audit['sun_program_dir']}")
    print(f"Reference available: {audit['reference_available']}")
    print(f"Status: {audit['status']}")
    print(f"Exact Stage 2 locked: {audit['exact_stage2_locked']}")
    if audit["required_missing"]:
        print("Missing required Stage 2 signatures:")
        for item in audit["required_missing"]:
            print(f"  - {item}")
    print()
    for indicator in audit["indicators"]:
        required = "required" if indicator["required_for_exact_stage2"] else "supporting"
        print(f"{indicator['id']}: {indicator['status']} ({required})")
        print(f"  {indicator['description']}")
        for evidence in indicator["evidence_files"][:8]:
            print(f"  - {evidence}")
        if len(indicator["evidence_files"]) > 8:
            print(f"  - ... {len(indicator['evidence_files']) - 8} more")
        print()
    print(audit["interpretation"])
