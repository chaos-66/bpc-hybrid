# -*- coding: utf-8 -*-
"""Build Experiment E same-data input contract v2 (zero API, corrected).

v1 problem (fixed): v1 counted 38 "non-empty" records from the raw Barrientos
artifact JSONs, which (a) included ``-``/empty placeholder texts, (b) treated
versioned duplicate IDs (r14 v1/v2) as duplicates, and (c) was not tied to the
frozen S2.11/S2.12 experiment surface.

v2 contract (this file):
* DERIVES THE 36 RECORDS FROM THE FROZEN S2.12 INPUT
  (``data/input/s2_12_complex_corpus_formal_input_v1.json``) — the frozen,
  Gold-blind, 36-record complex corpus — NOT from the raw artifact JSONs.
* Every record gets a UNIQUE versioned ID ``r10v1`` / ``r10v2``
  (record_id + version), so ``sample_id`` and the human-usable ID are both
  unique (36/36).
* No empty/``-``/placeholder texts (frozen input contains only real texts).
* Every record binds: source file path, source file SHA-256, text SHA-256,
  text byte size, record_id, version, and the S2.11 formal Gold sample_id.
* Validation (fail-closed, tested): duplicate IDs rejected; placeholder text
  rejected; a record missing from the frozen set rejected; an extra record
  not in the frozen set rejected.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

S212_INPUT = ROOT / "data/input/s2_12_complex_corpus_formal_input_v1.json"
S211_GOLD = ROOT / "data/gold/stage2/s2_11_complex_corpus_formal_gold_v1.json"
OUT = ROOT / "configs" / "ablations" / "e_same_data_input_contract_v2.json"


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _versioned_id(record_id: str, version: int) -> str:
    """Unique human-usable ID: r10v1 / r10v2 (fits the same surface the
    frozen corpus uses)."""
    return f"{record_id}v{version}"


def build() -> dict:
    s212 = json.loads(S212_INPUT.read_text(encoding="utf-8"))
    gold = json.loads(S211_GOLD.read_text(encoding="utf-8"))

    if s212.get("dataset_id") != "s2_11_barrientos_complex_corpus_36_v1":
        raise RuntimeError("S2.12 input dataset_id drift")
    if len(s212["records"]) != 36:
        raise RuntimeError("S2.12 input must contain exactly 36 records")

    gold_by_id = {r["sample_id"]: r for r in gold["records"]}
    if len(gold_by_id) != 36:
        raise RuntimeError("S2.11 Gold must contain 36 records")

    items: list[dict] = []
    seen_ids: set[str] = set()
    for rec in s212["records"]:
        sample_id = rec["sample_id"]
        source = rec["source"]
        record_id = source["record_id"]
        version = source["version"]
        vid = _versioned_id(record_id, version)
        if vid in seen_ids:
            raise RuntimeError(f"duplicate versioned id: {vid}")
        seen_ids.add(vid)
        if sample_id not in gold_by_id:
            raise RuntimeError(f"sample {sample_id} missing from S2.11 Gold")

        # Re-read the actual text from the bound artifact file (read-only)
        # and verify the hash binding.
        rel_path = source["path"]
        text_path = (ROOT.parent / rel_path).resolve()
        doc = json.loads(text_path.read_text(encoding="utf-8"))
        texts = {}
        for req in doc:
            rid = req.get("ID")
            ver = req.get("version", 1)
            texts[(rid, ver)] = (req.get("text") or "").strip()
        text = texts.get((record_id, version), "")
        if not text or text == "-":
            raise RuntimeError(
                f"placeholder/empty text for {vid} ({sample_id}); frozen "
                f"input must not reference placeholders")
        if _sha256_bytes(text.encode("utf-8")) != source["text_sha256"]:
            raise RuntimeError(f"text hash mismatch for {vid}")

        items.append({
            "id": vid,
            "sample_id": sample_id,
            "scenario": sample_id.split("/", 1)[0],
            "record_id": record_id,
            "version": version,
            "text": text,
            "bindings": {
                "source_file": rel_path,
                "source_file_sha256": _sha256_file(text_path),
                "text_sha256": source["text_sha256"],
                "text_byte_size": source.get("text_byte_size",
                                             len(text.encode("utf-8"))),
                "gold_sample_id": sample_id,
                "gold_sha256": _sha256_file(S211_GOLD),
            },
        })

    # fail-closed: exactly 36 unique items, no placeholder, ids unique
    ids = [i["id"] for i in items]
    if len(ids) != len(set(ids)):
        raise RuntimeError("non-unique versioned ids")
    if any(not i["text"] or i["text"] == "-" for i in items):
        raise RuntimeError("placeholder text present")
    if len(items) != 36:
        raise RuntimeError(f"expected 36 items, got {len(items)}")

    contract = {
        "schema_version": "e_same_data_input_contract@2.0.0",
        "task_id": "S2-BARRIENTOS-E",
        "claim_scope": "development_only",
        "zero_api": True,
        "supersedes": "configs/ablations/e_same_data_input_contract_v1.json",
        "fix_note": (
            "v1 wrongly counted 38 non-empty records from the raw artifact "
            "JSONs (included '-' placeholder texts; versioned rows appear as "
            "duplicates). v2 derives the 36 records from the FROZEN S2.12 "
            "complex corpus input and binds each to its S2.11 Gold sample_id."),
        "input_surface": {
            "frozen_input": "data/input/s2_12_complex_corpus_formal_input_v1.json",
            "frozen_input_sha256": _sha256_file(S212_INPUT),
            "frozen_gold": "data/gold/stage2/s2_11_complex_corpus_formal_gold_v1.json",
            "frozen_gold_sha256": _sha256_file(S211_GOLD),
            "count": len(items),
            "unique_ids": 36,
            "items": items,
        },
        "arms": {
            "E-ours": {
                "prompt": "prompts/sun_compat/direct_llm_sun_record_prompt_v6_d1r1_2026_08_05.md",
                "status": "ready_to_execute",
            },
            "E-barrientos-faithful": {
                "prompt": "references/barrientos_2026/artifact_input/prompts/formalize_requirements_prompt.txt",
                "format": "references/barrientos_2026/artifact_input/formats/compliance_requirements_format.json",
                "status": "ready_to_execute",
            },
            "E-module-swapped": {
                "prompt": "prompts/sun_compat/ablation_v1/direct_llm_barrientos_style_prompt_v1.md",
                "note": ("ours execution chain with the prompt/schema "
                         "representation module swapped to a Barrientos-style "
                         "six-field adapter; six-field schema/evaluator kept"),
                "status": "ready_to_execute",
            },
        },
        "shared_metrics_protocol": [
            "obligation/permission/prohibition three-class modality",
            "modality accuracy / macro-F1 / per-class F1",
            "JSON/structural validity rate",
            "output coverage",
            "failure rate",
            "runtime/cost (with per-arm usage)",
            "five-run self-consistency (E-ours / E-barrientos-faithful)",
            "sample-level agreement",
            "most/least stable cases",
        ],
        "separate_metrics_protocol": {
            "E-ours": [
                "actor/action/condition/constraint/exception P/R/F1",
                "overall micro P/R/F1",
                "evidence-span re-anchor rate",
                "actor-action map",
                "definition coverage",
            ],
            "E-barrientos-faithful": [
                "44-pattern / change-impact representation coverage",
                "Barrientos artifact evaluator original metrics",
                "strict JSON and self-consistency",
            ],
            "note": "task-specific metrics MUST be reported in separate tables; never merged into one F1",
        },
        "safety": {
            "llm_api_calls": 0,
            "network_calls": 0,
            "gold_modified": False,
            "references_read_only": True,
            "frozen_input_binding": True,
        },
    }
    return contract


def main() -> int:
    if OUT.exists():
        raise RuntimeError(f"refusing to overwrite: {OUT}")
    contract = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(contract, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8")
    print(f"E v2 contract written: {OUT.relative_to(ROOT)} "
          f"({contract['input_surface']['count']} unique records)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())