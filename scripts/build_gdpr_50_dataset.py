"""Build a 50-sample GDPR normative sentence dataset.

Step 1 of the four-step plan:
  - Extract text from GDPR PDF
  - Split into sentences using spaCy
  - Filter for normative sentences (containing modal verbs or legal markers)
  - Select 50 diverse sentences covering multiple GDPR articles
  - Annotate with 6 Sun-style fields: modality, actor, action, condition, constraint, exception
  - Output as candidate JSONL + gold JSONL

Usage:
    python scripts/build_gdpr_50_dataset.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pdfplumber
import spacy


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PDF_PATH = PROJECT_ROOT / "data" / "formal" / "raw" / "gdpr_eurlex" / "gdpr_2016_679_eurlex.pdf"
CANDIDATE_OUT = PROJECT_ROOT / "data" / "formal" / "r15_gdpr50" / "r15_gdpr50_candidate_samples.jsonl"
GOLD_OUT = PROJECT_ROOT / "data" / "formal" / "r15_gdpr50" / "r15_gdpr50_gold.jsonl"

# Modal verbs and legal markers for normative sentence filtering
MODAL_MARKERS = [
    r"\bshall\b", r"\bmust\b", r"\bmay\b", r"\bshould\b",
    r"\bshall not\b", r"\bmust not\b", r"\bmay not\b",
    r"\bis required\b", r"\bis prohibited\b", r"\bis permitted\b",
    r"\bis obliged\b", r"\bis entitled\b",
    r"\bhave the right\b", r"\bhave a right\b",
    r"\bunder no circumstances\b",
]

# Minimum sentence length (characters) to filter out noise
MIN_SENT_LENGTH = 60
MAX_SENT_LENGTH = 600

# Target count
TARGET_COUNT = 50


# ---------------------------------------------------------------------------
# Step 1: Extract text from PDF
# ---------------------------------------------------------------------------

def extract_pdf_text(pdf_path: Path) -> str:
    """Extract all text from the GDPR PDF."""
    print(f"Extracting text from {pdf_path}...")
    with pdfplumber.open(pdf_path) as pdf:
        text_parts = []
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)
    full_text = "\n\n".join(text_parts)
    print(f"  Extracted {len(full_text)} characters from {len(text_parts)} pages.")
    return full_text


# ---------------------------------------------------------------------------
# Step 2: Sentence splitting with spaCy
# ---------------------------------------------------------------------------

def split_sentences(text: str, nlp) -> list[str]:
    """Split text into sentences using spaCy."""
    # Process in chunks to avoid memory issues
    chunk_size = 100_000
    sentences = []
    for i in range(0, len(text), chunk_size):
        chunk = text[i:i + chunk_size]
        doc = nlp(chunk)
        for sent in doc.sents:
            s = sent.text.strip()
            if s:
                sentences.append(s)
    print(f"  Split into {len(sentences)} raw sentences.")
    return sentences


# ---------------------------------------------------------------------------
# Step 3: Filter normative sentences
# ---------------------------------------------------------------------------

def is_normative(sentence: str) -> bool:
    """Check if a sentence contains normative/legal markers."""
    text_lower = sentence.lower()
    for pattern in MODAL_MARKERS:
        if re.search(pattern, text_lower):
            return True
    return False


def is_good_length(sentence: str) -> bool:
    """Check sentence length is within bounds."""
    return MIN_SENT_LENGTH <= len(sentence) <= MAX_SENT_LENGTH


def filter_sentences(sentences: list[str]) -> list[str]:
    """Filter sentences for normative content and good length."""
    filtered = []
    seen_texts = set()
    for s in sentences:
        # Normalize whitespace
        s_clean = re.sub(r"\s+", " ", s).strip()
        # Deduplicate
        if s_clean in seen_texts:
            continue
        seen_texts.add(s_clean)
        # Filter
        if is_normative(s_clean) and is_good_length(s_clean):
            filtered.append(s_clean)
    print(f"  Filtered to {len(filtered)} normative sentences.")
    return filtered


# ---------------------------------------------------------------------------
# Step 4: Select diverse sentences
# ---------------------------------------------------------------------------

def detect_article(sentence: str) -> str | None:
    """Try to detect which GDPR article a sentence refers to."""
    m = re.search(r"Article\s+(\d+)", sentence, re.IGNORECASE)
    if m:
        return f"Article {m.group(1)}"
    m = re.search(r"Art\.\s*(\d+)", sentence, re.IGNORECASE)
    if m:
        return f"Article {m.group(1)}"
    return None


def classify_modality(sentence: str) -> str:
    """Rule-based modality classification."""
    text_lower = sentence.lower()
    # Priority order: prohibition > obligation > permission > definition
    if re.search(r"\bshall not\b|\bmust not\b|\bmay not\b|\bis prohibited\b|\bprohibit", text_lower):
        return "prohibition"
    if re.search(r"\bshall\b|\bmust\b|\bis required\b|\bis obliged\b", text_lower):
        return "obligation"
    if re.search(r"\bmay\b|\bis permitted\b|\bis entitled\b|\bhave the right\b|\bhave a right\b", text_lower):
        return "permission"
    if re.search(r"\bmeans\b|\brefers to\b|\bdefined as\b|\bdefinition\b", text_lower):
        return "definition"
    return "obligation"  # default for normative sentences


def select_diverse(sentences: list[str], target: int) -> list[str]:
    """Select diverse sentences, trying to cover multiple articles."""
    # Group by detected article
    by_article: dict[str | None, list[str]] = {}
    for s in sentences:
        art = detect_article(s)
        by_article.setdefault(art, []).append(s)

    selected = []
    # First pass: take up to 3 from each article
    article_keys = sorted(by_article.keys(), key=lambda x: (x is None, x or ""))
    for art in article_keys:
        pool = by_article[art]
        take = min(3, len(pool), target - len(selected))
        selected.extend(pool[:take])
        if len(selected) >= target:
            break

    # Second pass: fill remaining from unselected
    if len(selected) < target:
        selected_set = set(selected)
        for s in sentences:
            if s not in selected_set:
                selected.append(s)
                selected_set.add(s)
                if len(selected) >= target:
                    break

    return selected[:target]


# ---------------------------------------------------------------------------
# Step 5: Annotate sentences
# ---------------------------------------------------------------------------

def extract_actor(sentence: str) -> str | None:
    """Extract actor from sentence using heuristics."""
    text = sentence
    # Look for "the controller", "the processor", "the data subject", etc.
    actor_patterns = [
        r"(?:the\s+)?(?:controller|processor|data subject|supervisory authority|recipient|third party|natural person|legal person)",
        r"(?:the\s+)?(?:controller or processor|each controller|each processor)",
    ]
    for pat in actor_patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return m.group(0).strip()
    # Look for subject of the sentence
    m = re.match(r"^(The|A|Each|Any)\s+(\w+(?:\s+\w+)?)\s+(shall|must|may|should|is)", text, re.IGNORECASE)
    if m:
        return m.group(0).split(m.group(3))[0].strip()
    return None


def extract_action(sentence: str, modality: str) -> str | None:
    """Extract main action from sentence."""
    # Remove modal verb and get the main verb phrase
    text = sentence
    # Pattern: "shall/must/may <verb phrase>"
    m = re.search(r"\b(?:shall|must|may|should)\s+(not\s+)?(?:be\s+)?(\w+(?:\s+\w+){0,8})", text, re.IGNORECASE)
    if m:
        neg = m.group(1) or ""
        verb_phrase = m.group(2).strip()
        return f"{neg}{verb_phrase}".strip()
    return None


def extract_condition(sentence: str) -> str | None:
    """Extract condition phrases."""
    patterns = [
        r"(?:Where|If|When|In case of|Provided that|On condition that)\s+[^,.;]+(?:,|;|\.)",
        r"(?:where|if|when)\s+[^,.;]+(?:,|;|\.)",
    ]
    for pat in patterns:
        m = re.search(pat, sentence, re.IGNORECASE)
        if m:
            return m.group(0).rstrip(",;.").strip()
    return None


def extract_constraint(sentence: str) -> str | None:
    """Extract constraint information."""
    # Look for temporal, quantitative, or qualitative constraints
    patterns = [
        r"(?:within|before|after|at least|at most|no later than|not later than)\s+[^,.;]+",
        r"(?:in accordance with|subject to|without prejudice to)\s+[^,.;]+",
    ]
    for pat in patterns:
        m = re.search(pat, sentence, re.IGNORECASE)
        if m:
            return m.group(0).strip()
    return None


def extract_exception(sentence: str) -> str | None:
    """Extract exception phrases."""
    patterns = [
        r"(?:except|unless|with the exception of|apart from|other than|excluding)\s+[^.;]+",
        r"(?:except where|unless where)\s+[^.;]+",
    ]
    for pat in patterns:
        m = re.search(pat, sentence, re.IGNORECASE)
        if m:
            return m.group(0).rstrip(";.").strip()
    return None


def annotate_sentence(sample_id: str, sentence: str, idx: int) -> dict:
    """Annotate a single sentence with Sun-style fields."""
    modality = classify_modality(sentence)
    actor = extract_actor(sentence)
    action = extract_action(sentence, modality)
    condition = extract_condition(sentence)
    constraint = extract_constraint(sentence)
    exception = extract_exception(sentence)

    # Detect article
    article = detect_article(sentence)

    candidate = {
        "sample_id": sample_id,
        "domain": "GDPR",
        "source": "gdpr_eurlex_pdf_extraction",
        "evidence_scope": "real GDPR text extracted from EUR-Lex PDF",
        "is_real_legal_text": True,
        "is_public_benchmark": False,
        "not_sun_dataset": True,
        "text": sentence,
        "design_tags": [modality],
        "notes": f"GDPR {article or 'unknown article'}. Extracted from EUR-Lex PDF."
    }

    gold = {
        "sample_id": sample_id,
        "domain": "GDPR",
        "source": "gdpr_eurlex_pdf_extraction",
        "gold_fields": {
            "modality": {
                "value": modality,
                "applicable": True,
                "notes": f"Rule-based classification: {modality}."
            },
            "actor": {
                "value": actor,
                "applicable": actor is not None,
                "notes": "Extracted via heuristic patterns."
            },
            "action": {
                "value": action,
                "applicable": action is not None,
                "notes": "Extracted via modal verb + verb phrase pattern."
            },
            "condition": {
                "value": condition,
                "applicable": condition is not None,
                "notes": "Extracted via conditional marker patterns."
            },
            "constraint": {
                "value": constraint,
                "applicable": constraint is not None,
                "notes": "Extracted via constraint marker patterns."
            },
            "exception": {
                "value": exception,
                "applicable": exception is not None,
                "notes": "Extracted via exception marker patterns."
            },
        },
        "annotation_status": "auto_annotated_rule_based_pending_review",
        "claim_boundary": "auto-annotated GDPR dataset for experiment"
    }

    return candidate, gold


# ---------------------------------------------------------------------------
# Step 6: Write outputs
# ---------------------------------------------------------------------------

def write_jsonl(path: Path, records: list[dict]) -> None:
    """Write records to a JSONL file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"  Written {len(records)} records to {path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("=== Building 50-sample GDPR Dataset ===\n")

    # Step 1: Extract PDF text
    if not PDF_PATH.exists():
        print(f"ERROR: PDF not found at {PDF_PATH}")
        sys.exit(1)
    full_text = extract_pdf_text(PDF_PATH)

    # Step 2: Load spaCy and split sentences
    print("\nLoading spaCy model...")
    nlp = spacy.load("en_core_web_sm")
    nlp.max_length = 2_000_000
    sentences = split_sentences(full_text, nlp)

    # Step 3: Filter normative sentences
    print("\nFiltering normative sentences...")
    normative = filter_sentences(sentences)

    if len(normative) < TARGET_COUNT:
        print(f"  WARNING: Only {len(normative)} normative sentences found (target: {TARGET_COUNT})")
        print("  Will use all available sentences.")

    # Step 4: Select diverse sentences
    print("\nSelecting diverse sentences...")
    selected = select_diverse(normative, TARGET_COUNT)
    print(f"  Selected {len(selected)} sentences.")

    # Print article distribution
    article_counts: dict[str, int] = {}
    for s in selected:
        art = detect_article(s) or "unknown"
        article_counts[art] = article_counts.get(art, 0) + 1
    print("  Article distribution:")
    for art, count in sorted(article_counts.items()):
        print(f"    {art}: {count}")

    # Step 5: Annotate
    print("\nAnnotating sentences...")
    candidates = []
    golds = []
    for i, sentence in enumerate(selected, 1):
        sample_id = f"r15_gdpr50_{i:03d}"
        cand, gold = annotate_sentence(sample_id, sentence, i)
        candidates.append(cand)
        golds.append(gold)

    # Step 6: Write outputs
    print("\nWriting outputs...")
    write_jsonl(CANDIDATE_OUT, candidates)
    write_jsonl(GOLD_OUT, golds)

    # Summary
    modality_dist = {}
    for g in golds:
        m = g["gold_fields"]["modality"]["value"]
        modality_dist[m] = modality_dist.get(m, 0) + 1
    print("\n  Modality distribution:")
    for m, count in sorted(modality_dist.items()):
        print(f"    {m}: {count}")

    print(f"\n=== Done. {len(candidates)} samples created. ===")
    print(f"  Candidates: {CANDIDATE_OUT}")
    print(f"  Gold:       {GOLD_OUT}")
    print("\n  NOTE: Gold annotations are auto-generated and need manual review.")


if __name__ == "__main__":
    main()
