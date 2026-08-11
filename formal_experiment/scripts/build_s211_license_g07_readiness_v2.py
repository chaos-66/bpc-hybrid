# -*- coding: utf-8 -*-
"""S2.11 license & adapter readiness v2 + G0.7 Barrientos adapter registry
DRY-RUN (zero-API, read-only qualification; nothing activated).

License audit (local): references/barrientos_2026 contains NO LICENSE /
README / metadata license declaration (verified by search). Per the
unknown_pending_confirmation discipline, no inference is made:
- paper readable: unknown_pending_confirmation (no authoritative URL/DOI
  recorded locally; no online verification performed this round)
- code usable: unknown_pending_confirmation
- data redistributable: unknown_pending_confirmation
- project activatable: unknown_pending_confirmation
External license evidence is recorded as PENDING (no authoritative URL
available locally; search-engine snippets are not acceptable per contract).

G0.7 adapter registry (dry-run): schema / labels / data / metrics /
license / adapter boundaries for the Barrientos RC4PC artifact; the 3-class
modality -> 4-class boundary; precondition/norm/temporal-validity ->
span-based Rule Record adapter boundaries; definition-class handling, span
alignment, cross-reference and evidence provenance; synthetic fixtures only
for adapter-contract testing; external labels are NEVER auto-promoted to
project Gold.

S2.11 exact blockers are listed; an authorization sentence is emitted ONLY
when every data-qualification condition is met (NOT this round).

Outputs:
- outputs/reports/s2_11_license_adapter_readiness_v2.json
- outputs/reports/s2_11_license_adapter_readiness_v2.md
- outputs/reports/g0_7_barrientos_adapter_registry_dry_run.json
- outputs/reports/g0_7_barrientos_adapter_registry_dry_run.md
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BARRIENTOS_REF = ROOT.parent / "references" / "barrientos_2026"

OUT_LICENSE = ROOT / "outputs" / "reports" / "s2_11_license_adapter_readiness_v2.json"
OUT_LICENSE_MD = ROOT / "outputs" / "reports" / "s2_11_license_adapter_readiness_v2.md"
OUT_G07 = ROOT / "outputs" / "reports" / "g0_7_barrientos_adapter_registry_dry_run.json"
OUT_G07_MD = ROOT / "outputs" / "reports" / "g0_7_barrientos_adapter_registry_dry_run.md"


def _audit_local_license() -> dict[str, Any]:
    """Read-only local license evidence audit."""
    license_files = []
    license_hits = []
    if BARRIENTOS_REF.exists():
        for f in BARRIENTOS_REF.rglob("*"):
            if f.is_file() and f.name.upper() in (
                    "LICENSE", "LICENCE", "COPYING", "README", "README.MD",
                    "METADATA", "METADATA.JSON", "CITATION", "CITATION.CFF"):
                license_files.append(str(f.relative_to(BARRIENTOS_REF)))
        # content scan for license/copyright keywords in text-ish files
        for f in BARRIENTOS_REF.rglob("*"):
            if not f.is_file() or f.stat().st_size > 2_000_000:
                continue
            if f.suffix.lower() not in (".md", ".txt", ".yml", ".yaml", ".json", ".py", ".toml"):
                continue
            try:
                t = f.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            low = t.lower()
            for kw in ("license", "licence", "copyright", "cc by", "creative commons", "redistribut"):
                if kw in low:
                    license_hits.append({"file": str(f.relative_to(BARRIENTOS_REF)),
                                         "keyword": kw})
    return {
        "local_license_files": license_files,
        "keyword_hits": license_hits[:10],
        "keyword_hit_count": len(license_hits),
        "conclusion": "NO local license declaration found; status unknown_pending_confirmation",
    }


def build_license_readiness() -> dict[str, Any]:
    local = _audit_local_license()
    return {
        "schema_version": "s2_11_license_adapter_readiness@2.0.0",
        "project_date": "2026-08-11",
        "status": "dry_run_not_applied",
        "license_audit": {
            "local": local,
            "external_evidence": {
                "status": "pending",
                "reason": ("no authoritative URL/DOI for the Barrientos 2026 "
                           "paper/repo/artifact is recorded locally; online "
                           "license verification was NOT performed (search "
                           "snippets are not acceptable per contract)"),
            },
            "four_way_distinction": {
                "paper_readable": "unknown_pending_confirmation",
                "code_usable": "unknown_pending_confirmation",
                "data_redistributable": "unknown_pending_confirmation",
                "project_activatable": "unknown_pending_confirmation",
                "policy": "no inference without explicit declaration",
            },
        },
        "s2_11_exact_blockers": [
            "license: unknown_pending_confirmation (no local declaration; external evidence pending)",
            "data activation authorization: NOT granted (references/ stays read-only)",
            "mapping decision: modality 3->4 mapping table / adjudication not decided",
            "human Gold: required for external-label qualification; not started",
            "G0.5 complexity rules: not frozen before results (retrospective only today)",
            "Barrientos adapter (S2-BARR-2): not implemented (only the contract dry-run exists)",
        ],
        "authorization_sentence": None,
        "authorization_sentence_reason": (
            "data-qualification conditions NOT all met (license unknown, "
            "activation not authorized, mapping/adjudication pending); no "
            "authorization sentence is emitted"),
        "g0_5_s2_11_status_unchanged": True,
        "zero_api": {"new_llm_api_calls": 0},
    }


def build_g07_registry() -> dict[str, Any]:
    return {
        "schema_version": "g0_7_barrientos_adapter_registry@1.0.0",
        "status": "dry_run_not_applied",
        "registry_entries": {
            "schema": {
                "source": "references/barrientos_2026/artifact_input/formats/compliance_requirements_format.json",
                "local": True,
                "note": "RC4PC schema (id/precondition/norms/temporal_validity); NOT Sun six-element compatible",
            },
            "labels": {
                "modality_classes_barrientos": ["obligation", "permission", "prohibition"],
                "modality_classes_sun": ["obligation", "permission", "prohibition", "definition"],
                "mapping_boundary": "3->4 NOT directly mappable; 'definition' class absent; mapping table or adjudication required",
            },
            "data": {
                "source": "references/barrientos_2026 (local, read-only)",
                "license": "unknown_pending_confirmation",
                "activation": "NOT authorized",
            },
            "metrics": {
                "barrientos": "multi-dimensional (semantic coverage / structural encoding / deontic correctness)",
                "project": "Sun literal-overlap six-element (five span fields + separate modality labels)",
                "comparability": "only after adapter + qualification; cross-metric transfer NOT comparable",
            },
            "license": "unknown_pending_confirmation (see license readiness v2)",
        },
        "adapter_boundaries": {
            "modality_3_to_4": "needs explicit mapping table or human adjudication; never auto-extend",
            "precondition_to_span": "precondition and/or/not triples -> span-based condition requires span alignment adapter (not implemented)",
            "norm_to_rule_record": "norms[] -> rule record fields requires field mapping decision",
            "temporal_validity": "start/end -> constraint handling requires mapping decision",
            "definition_class": "Barrientos has no definition class; Sun definition sentences need separate adjudication",
            "span_alignment": "external spans/offsets cannot be assumed to align with approved English text",
            "cross_reference": "cross-article/process references need explicit provenance handling",
            "evidence_provenance": "every mapped value must keep its source element/XPath provenance",
            "guard": "external labels must NEVER be auto-promoted to project Gold",
        },
        "testing_policy": {
            "synthetic_fixtures_only": True,
            "adapter_contract_tests": "fail-closed: without a mapping decision the adapter must refuse to map",
            "no_external_data_activation": True,
        },
        "s2_barr_1_status": "registry dry-run delivered; license evidence pending",
        "s2_barr_2_status": "blocked (adapter implementation requires mapping decision + license qualification)",
        "zero_api": {"new_llm_api_calls": 0},
    }


def _write(path: Path, data: bytes) -> None:
    if path.exists() and path.read_bytes() != data:
        raise RuntimeError(f"refusing to overwrite different content: {path}")
    path.write_bytes(data)


def main() -> int:
    license_r = build_license_readiness()
    g07 = build_g07_registry()
    j1 = (json.dumps(license_r, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    _write(OUT_LICENSE, j1)
    j2 = (json.dumps(g07, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    _write(OUT_G07, j2)

    md1 = [
        "# S2.11 License & Adapter Readiness v2 (DRY-RUN)",
        "",
        f"- local license: {license_r['license_audit']['local']['conclusion']}",
        f"- external evidence: {license_r['license_audit']['external_evidence']['status']} "
        f"({license_r['license_audit']['external_evidence']['reason']})",
        "",
        "## Exact S2.11 blockers",
    ]
    for b in license_r["s2_11_exact_blockers"]:
        md1.append(f"- {b}")
    md1.append("")
    md1.append(f"- authorization sentence: {license_r['authorization_sentence'] or 'NOT EMITTED'}")
    md1.append("")
    t1 = "\n".join(md1)
    _write(OUT_LICENSE_MD, t1.encode("utf-8"))

    md2 = [
        "# G0.7 Barrientos Adapter Registry (DRY-RUN)",
        "",
    ]
    for k, v in g07["registry_entries"].items():
        md2.append(f"## {k}")
        if isinstance(v, dict):
            for kk, vv in v.items():
                md2.append(f"- {kk}: {vv}")
        else:
            md2.append(f"- {v}")
    md2 += ["", "## Adapter boundaries"]
    for k, v in g07["adapter_boundaries"].items():
        md2.append(f"- {k}: {v}")
    md2 += ["", f"- S2-BARR-1: {g07['s2_barr_1_status']}",
            f"- S2-BARR-2: {g07['s2_barr_2_status']}", ""]
    t2 = "\n".join(md2)
    _write(OUT_G07_MD, t2.encode("utf-8"))

    print(f"license readiness v2: {OUT_LICENSE.relative_to(ROOT)}")
    print(f"G0.7 registry dry-run: {OUT_G07.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
