# data/formal/ — Formal Dataset Storage

## Directory Purpose

This directory and its subdirectories hold **formal (non-synthetic) evaluation data**
after R12 closed as a synthetic prototype API-pipeline sanity milestone.

**R13.0 is planning only.  No data has been downloaded yet.**

## Subdirectories

| Directory | Purpose | Status |
|-----------|---------|--------|
| `raw/` | Original downloaded files — never modified | Empty (planning stage) |
| `processed/` | Cleaned, sentence-split, ID-assigned `.jsonl` for model input | Empty |
| `gold/` | Gold annotations, labels, answer keys | Empty |
| `metadata/` | Source records, license files, processing changelog | Empty |

## Safety Rules

**Do NOT place any of the following in this directory tree:**

- API keys, access tokens, bearer tokens
- Cookies or session data
- Account usernames or passwords
- Personal data of individuals (names, emails, addresses)
- Data with unknown or unconfirmed license
- Proprietary data without explicit written permission

## Data Intake Workflow (Future)

1. User locates and verifies a candidate dataset (see `docs/dataset_sources.md`).
2. User places original files in `data/formal/raw/`.
3. User creates `data/formal/metadata/sources.json` recording URL, license, download date.
4. R13.1 processes raw files into `data/formal/processed/` (`.jsonl` format with IDs).
5. Gold annotations go to `data/formal/gold/`.
6. No real API calls until dataset, gold, and plan are Codex-accepted.

## Relationship to data/prototype/

`data/prototype/` contains synthetic prototype data used during R5–R12 phases.
It is **not** a formal dataset.  It must not be modified during R13+.

Formal evaluation data must live here in `data/formal/` and remain separate from
the prototype data.
