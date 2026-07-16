"""Low-risk text cleaning for the EStG-150 raw German OCR.

Allowed cleaning (intentionally narrow):
  - Unicode NFC normalization
  - whitespace collapse (runs of spaces/tabs -> single space)
  - collapse hyphen-at-line-break patterns where the join matches a small
    whitelist of known German words (e.g. "Rechtsnachfol-\nger" ->
    "Rechtsnachfolger"); otherwise the record is flagged for human review
    and the text is NOT auto-merged.

Anything that could change legal meaning, clause boundaries, or
membership is left untouched and flagged.

It also joins in the candidate English translation from
estg_selected_150_en_llm_translated.jsonl so the canonical review file can
present raw_de / cleaned_de / candidate_en side by side.

Run from formal_experiment/ as:
    python scripts/clean_estg150_german.py --dry-run
    python scripts/clean_estg150_german.py --write

It never edits the input files. The prepared output is written to
data/development/estg/estg_150_prepared_v1.jsonl only on `--write`.
"""
import argparse
import hashlib
import json
import re
import unicodedata
from pathlib import Path

BASE = Path(__file__).resolve().parents[1] / "data" / "development" / "estg"
SOURCE = BASE / "estg_selected_150_de.jsonl"
SOURCE_EN = BASE / "estg_selected_150_en_llm_translated.jsonl"
DEST = BASE / "estg_150_prepared_v1.jsonl"

# A small whitelist of common German words formed by joining halves split
# across a line break in the source PDF. Only used as a permissive check:
# if a candidate join is in the whitelist we mark it "high_confidence";
# otherwise we leave the text unchanged and flag for human review.
KNOWN_SPLIT_JOINS = {
    "anschaffungskosten",
    "unentgeltlich",
    "rechtsnachfolger",
    "betriebsinhabers",
    "wirtschaftsgut",
    "unternehmer",
    "mitunternehmer",
    "anschaffungskosten",
    "fiktive",
    "buchwerte",
    "buchwertfortfuhrung",
    "buchwertfortführung",
    "gemeinschaft",
    "einkunfte",
    "einkünfte",
    "veranlagung",
    "einkommensteuer",
    "einkommen",
    "verluste",
    "gewinne",
    "gesellschafters",
    "gesellschaft",
    "veranlagungszeitraum",
}


def normalize_nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text)


_WS = re.compile(r"[ \t]+")
_NEWLINE = re.compile(r"\n+")


def collapse_whitespace(text: str) -> str:
    # We do NOT touch single newlines because they can be clause boundaries.
    # We only collapse runs of horizontal whitespace inside a line.
    return _WS.sub(" ", text)


# A hyphen at the end of a line followed by a continuation on the next
# line is an OCR line-break artifact. We detect "word-\nword" patterns.
# We do NOT merge across blank lines (paragraph breaks).
_HYPHEN_BREAK = re.compile(r"(\w+)-\n(\w+)")


def candidate_hyphen_joins(text: str):
    """Yield (start, end, joined) for each candidate hyphen-join.

    Caller decides whether to apply the join.
    """
    for m in _HYPHEN_BREAK.finditer(text):
        joined = m.group(1) + m.group(2)
        yield m.start(), m.end(), joined


def clean_text(raw: str):
    """Return (cleaned, flags, joins_applied)."""
    flags = []
    text = normalize_nfc(raw)
    if text != raw:
        flags.append("unicode_nfc_normalized")

    ws_cleaned = collapse_whitespace(text)
    if ws_cleaned != text:
        flags.append("horizontal_whitespace_collapsed")
    text = ws_cleaned

    # Candidate hyphen-line-break joins. We apply them only when the join
    # matches a known word in the whitelist. Otherwise we mark the record
    # for human review and do NOT mutate the text.
    joins_applied = []
    out = []
    last = 0
    boundary_issue = False
    for start, end, joined in candidate_hyphen_joins(text):
        if joined.lower() in KNOWN_SPLIT_JOINS:
            joins_applied.append({
                "start": start,
                "end": end,
                "joined": joined,
            })
            out.append(text[last:start])
            out.append(joined)
            last = end
        else:
            boundary_issue = True
    if joins_applied:
        out.append(text[last:])
        text = "".join(out)
        flags.append("hyphen_linebreak_joined_known")

    if boundary_issue:
        flags.append("source_boundary_issue_candidate")

    return text, flags, joins_applied


def sha256(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true",
                    help="only print summary, do not write file")
    ap.add_argument("--write", action="store_true",
                    help="write cleaned candidate jsonl")
    args = ap.parse_args()
    if not args.dry_run and not args.write:
        args.dry_run = True

    with SOURCE.open(encoding="utf-8") as f:
        sel = [json.loads(line) for line in f if line.strip()]
    assert len(sel) == 150, f"expected 150 selected, got {len(sel)}"

    with SOURCE_EN.open(encoding="utf-8") as f:
        en = [json.loads(line) for line in f if line.strip()]
    assert len(en) == 150, f"expected 150 EN, got {len(en)}"
    en_by_id = {r["id"]: r["text_en"] for r in en}

    out_records = []
    n_changed = 0
    n_unicode = 0
    n_whitespace = 0
    n_joins = 0
    n_boundary = 0
    for r in sel:
        raw = r["text"]
        cleaned, flags, joins = clean_text(raw)
        if cleaned != raw:
            n_changed += 1
        if "unicode_nfc_normalized" in flags:
            n_unicode += 1
        if "horizontal_whitespace_collapsed" in flags:
            n_whitespace += 1
        if joins:
            n_joins += 1
        if "source_boundary_issue_candidate" in flags:
            n_boundary += 1
        out_records.append({
            "legacy_record_id": r["id"],
            "raw_text_de": raw,
            "raw_text_de_sha256": sha256(raw),
            "cleaned_text_de_candidate": cleaned,
            "cleaned_text_de_candidate_sha256": sha256(cleaned),
            "cleaning_flags": flags,
            "hyphen_joins_applied": joins,
            "candidate_text_en": en_by_id[r["id"]],
            "candidate_text_en_sha256": sha256(en_by_id[r["id"]]),
            "approved_text_en": None,
            "needs_adjudication": bool(flags and
                "source_boundary_issue_candidate" in flags),
        })

    summary = {
        "source": str(SOURCE.relative_to(SOURCE.parents[2])),
        "source_en": str(SOURCE_EN.relative_to(SOURCE_EN.parents[2])),
        "count": len(out_records),
        "n_text_changed": n_changed,
        "n_unicode_normalized": n_unicode,
        "n_whitespace_collapsed": n_whitespace,
        "n_hyphen_joins_applied": n_joins,
        "n_boundary_issue_candidate": n_boundary,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    if args.write:
        with DEST.open("w", encoding="utf-8") as f:
            for rec in out_records:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        print(f"Wrote {DEST}")


if __name__ == "__main__":
    main()
