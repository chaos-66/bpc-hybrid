# Search Log / Not-Found Notes

Date of search (environment clock): 2026-09-19/20 (tool logs show 2026 timestamps).

## APIs and sources used

- Crossref REST API: DOIs, authors, venue, page range, license, publisher links.
- ACL Anthology: landing pages, BibTeX, PDF downloads for LegalDiscourse and COLING 2025.
- arXiv API: Haque & Singh preprint metadata and PDF.
- Semantic Scholar web/reader: discovery of D/E/F/G records and OA PDF links.
- Unpaywall: OA location for RC4PC; found TU/e repository copy.
- TU/e Pure: RC4PC repository PDF and metadata.
- Springer: LegalChanges4BPC and Kölbel PDFs.
- MDPI: DPLACC page and PDF URL; direct download blocked by Access Denied.
- GitHub API and raw content: LegalChanges4BPC and contextIsKey repositories.
- Anonymous GitHub API: RC4PC repository file list, zip, and exact prompt.
- `r.jina.ai` publisher reader: fallback for MDPI, ScienceDirect, and some repository blocks; used only after direct access failed and cross-checked where possible.

## Not found after search

- LegalDiscourse public code/annotation package URL: not found.
- Haque & Singh public code/supplement: not found.
- COLING 2025 public code/supplement: not found.
- DPLACC public code repository: not found.
- Exact LegalChanges4BPC round-1 prompt without the one-shot example: not found in public git history or repository.
- Haque & Singh publisher version Figure 1: publisher full text not accessible; arXiv prompt verified instead.
- Sun X. et al. 2024 full text or prompt: closed access; not found.
- MDPI direct PDF: blocked; publisher reader text used.
- Any public paper with a span-level overlap/nesting annotation rule for condition vs constraint: not found.

## Source-verification caveats

- LegalDiscourse text was first read via Jina reader and later verified by direct ACL PDF download + PyMuPDF.
- LegalChanges4BPC exact prompt was read from GitHub raw and commit history; the paper describes a two-round design, but the public history did not expose an exact pre-example snapshot.
- RC4PC exact prompt was read from the anonymous repository; the repository is anonymous (submission artifact), not a named public GitHub repository.
- DPLACC was not treated as a full local PDF because the direct MDPI download was blocked.
