"""D1 Sol-candidate semantics pilot evaluation (2026-08-07).

Purpose:
    Compare, on the SAME 19 representative samples and the SAME golds
    (fine clause-level and sentence-level coarse variant), the D1-R3
    locked recipe (v6 prompt) against the Sol-candidate-semantics pilot
    (adapted historical Gold-candidate extraction prompt).  Both arms use
    fixed responses (no new LLM calls): v6 baseline = historical arm_b_v6
    responses; pilot arm = s27_d1_solcand_pilot_19_hist56d_v1
    d1_responses.jsonl.

Safeguards:
    - gold + coarse variant read from committed artifacts / git show
      56d2b03 (read-only); never overwrites anything;
    - no LLM/API/network call;
    - outputs go under outputs/development;
    - coarse gold identity enforced via semantic sha256 6e19cf3c... (same
      coarse gold as the B0/D1 granularity experiments).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bpc_hybrid.estg150_b0_development import (  # noqa: E402
    Estg150B0DevelopmentError,
    build_canonical_gold_records,
    sha256_file,
)
from bpc_hybrid.stage2_evaluation_v3 import membership_sha256  # noqa: E402
from bpc_hybrid.stage2_sun_literal_overlap import (  # noqa: E402
    evaluate_sun_literal_overlap,
)

SOURCE_COMMIT = "56d2b03"
DECLARED_MEMBERSHIP = "e8e6268644cbc9b7ed42bef19f2e2e2432633a306eab9bf009725ef9571785d7"
DATASET_ID = "independently_reconstructed_estg_150_v1"
METHOD_ID = "direct_llm"
EXPECTED_FINE_SEMANTIC_SHA256 = "5d7ec7f6d6611d9029840cbd92254f0b342c5b8ef8f5cd7f1d93493995d315a4"
EXPECTED_COARSE_SEMANTIC_SHA256 = "6e19cf3c684a26aa9e9fdc9f76c3529b5a4232aecb085fad4c206ceb177bcb26"

V6_BASELINE_RESPONSES = (
    ROOT
    / "outputs/development/s27_d1_pilot_20_hist56d_v1/arm_b_v6_20260805c"
    / "d1_responses.jsonl"
)
PILOT_RESPONSES = (
    ROOT / "outputs/development/s27_d1_solcand_pilot_19_hist56d_v1" / "d1_responses.jsonl"
)
PILOT_MANIFEST = (
    ROOT / "outputs/development/s27_d1_solcand_pilot_19_hist56d_v1" / "manifest.json"
)
DEFAULT_OUTPUT_DIR = ROOT / "outputs/development/s27_d1_solcand_pilot_19_hist56d_v1"

HISTORICAL_PATHS = {
    "layer_e": "formal_experiment/data/development/human_review/estg_150_human_correction_v1.json",
    "membership": "formal_experiment/data/development/estg/estg_150_membership_hashes.json",
}

FIELDS = ("modality", "actor", "action", "condition", "constraint", "exception")
PLURAL_KEYS = {
    "actor": "actors",
    "action": "actions",
    "condition": "conditions",
    "constraint": "constraints",
    "exception": "exceptions",
}


class PilotError(ValueError):
    """Raised when the pilot evaluation cannot proceed safely."""


def _git(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", *args],
        cwd=cwd or _git_root(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )


_GIT_ROOT: Path | None = None


def _git_root() -> Path:
    global _GIT_ROOT
    if _GIT_ROOT is None:
        completed = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        _GIT_ROOT = Path(completed.stdout.decode("utf-8").strip())
    return _GIT_ROOT


def git_show_bytes(commit: str, path: str) -> bytes:
    return _git("show", f"{commit}:{path}").stdout


def git_full_sha(commit: str) -> str:
    return _git("rev-parse", commit).stdout.decode("ascii").strip()


def semantic_hash_json(value: Any) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _normalized(text: str) -> str:
    return " ".join(text.casefold().split())


def _field_spans(record: Mapping[str, Any], field: str) -> list[dict[str, Any]]:
    spans: list[dict[str, Any]] = []
    for clause in record.get("clauses") or []:
        if not isinstance(clause, Mapping):
            raise PilotError("clause is not an object")
        if field == "modality":
            modality = clause.get("modality") or {}
            items = modality.get("evidence") or []
        else:
            items = clause.get(PLURAL_KEYS[field]) or []
        for item in items:
            if not isinstance(item, Mapping) or not isinstance(item.get("start"), int) or not isinstance(item.get("end"), int):
                raise PilotError(f"{field} span lacks integer start/end")
            spans.append(dict(item))
    return spans


def coarse_gold_record(record: Mapping[str, Any]) -> dict[str, Any]:
    """Sentence-level coarse variant; identical rule to the B0/D1
    granularity experiments (identity enforced by semantic sha below)."""
    sample_id = record.get("sample_id")
    source_text = record.get("source_text")
    if not isinstance(sample_id, str) or not isinstance(source_text, str) or not source_text:
        raise PilotError("record lacks sample_id or source_text")

    merged: dict[str, list[dict[str, Any]]] = {}
    modality_label: str | None = None
    for clause in record.get("clauses") or []:
        label = (clause.get("modality") or {}).get("label")
        if modality_label is None and isinstance(label, str) and label:
            modality_label = label
    for field in FIELDS:
        spans = _field_spans(record, field)
        if not spans:
            merged[field] = []
            continue
        start = min(item["start"] for item in spans)
        end = max(item["end"] for item in spans)
        if not (0 <= start < end <= len(source_text)):
            raise PilotError(f"{sample_id} {field} merged span outside sentence")
        text = source_text[start:end]
        span: dict[str, Any] = {
            "id": f"{sample_id}_sent_{field}",
            "text": text,
            "start": start,
            "end": end,
        }
        if field != "modality":
            span["normalized"] = _normalized(text)
        merged[field] = [span]

    sentence_clause: dict[str, Any] = {
        "clause_id": f"{sample_id}_sentence",
        "clause_span": {
            "text": source_text,
            "start": 0,
            "end": len(source_text),
        },
        "modality": {
            "label": modality_label,
            "evidence": merged["modality"],
        },
        "actor_action_map": [],
        "order_relations": [],
    }
    for field in ("actor", "action", "condition", "constraint", "exception"):
        sentence_clause[PLURAL_KEYS[field]] = merged[field]

    return {
        "schema_version": record.get("schema_version"),
        "sample_id": sample_id,
        "source_id": record.get("source_id"),
        "source_text": source_text,
        "clauses": [sentence_clause],
        "method": {"name": "coarse_sentence_level_variant", "schema_source": "b0_coarse_gold_sentence@1.0.0"},
        "validation": {"schema_valid": True, "cross_field_valid": True, "errors": []},
    }


def load_responses_jsonl(path: Path, *, label: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, raw in enumerate(handle, 1):
            if not raw.strip():
                continue
            try:
                row = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise PilotError(f"{label} line {line_number}: {exc}") from exc
            if not isinstance(row, dict):
                raise PilotError(f"{label} line {line_number}: not an object")
            rows.append(row)
    if not rows:
        raise PilotError(f"{label} is empty")
    return rows


def subset_responses(responses: Sequence[Mapping[str, Any]], sample_ids: set[str]) -> list[dict[str, Any]]:
    out = [dict(r) for r in responses if r.get("sample_id") in sample_ids]
    if len(out) != len(sample_ids):
        raise PilotError("response subset membership mismatch")
    return out


def count_gold_spans(gold: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {f: 0 for f in FIELDS}
    for record in gold:
        for field in FIELDS:
            counts[field] += len(_field_spans(record, field))
    return counts


def run(output_dir: Path, source_commit: str) -> int:
    output_dir = output_dir.resolve()
    try:
        output_dir.relative_to((ROOT / "outputs/development").resolve())
    except ValueError as exc:
        raise PilotError("output must remain under outputs/development") from exc

    commit_sha = git_full_sha(source_commit)
    with tempfile.TemporaryDirectory(
        prefix=f"solcand-pilot-{os.getpid()}-", dir=(ROOT / ".tmp")
    ) as raw_work:
        work_dir = Path(raw_work)
        for key, path in HISTORICAL_PATHS.items():
            (work_dir / key).write_bytes(git_show_bytes(source_commit, path))

        gold, _ = build_canonical_gold_records(
            work_dir / "layer_e", work_dir / "membership"
        )
        if len(gold) != 150:
            raise PilotError("canonical Gold must contain 150 records")
        if membership_sha256(gold) != DECLARED_MEMBERSHIP:
            raise PilotError("canonical Gold membership hash mismatch")
        fine_semantic = semantic_hash_json(gold)
        if fine_semantic != EXPECTED_FINE_SEMANTIC_SHA256:
            raise PilotError(f"fine Gold semantic sha256 mismatch: {fine_semantic}")

        coarse = [coarse_gold_record(r) for r in gold]
        coarse_semantic = semantic_hash_json(coarse)
        if coarse_semantic != EXPECTED_COARSE_SEMANTIC_SHA256:
            raise PilotError("coarse Gold semantic sha256 mismatch vs B0/D1 experiments")

        gold_by_id = {r["sample_id"]: r for r in gold}
        coarse_by_id = {r["sample_id"]: r for r in coarse}

        v6 = load_responses_jsonl(V6_BASELINE_RESPONSES, label="v6 baseline")
        pilot = load_responses_jsonl(PILOT_RESPONSES, label="solcand pilot")
        v6_ids = {r["sample_id"] for r in v6}
        pilot_ids = {r["sample_id"] for r in pilot}
        if v6_ids != pilot_ids:
            raise PilotError(
                f"membership differs: v6={len(v6_ids)} pilot={len(pilot_ids)}"
            )
        shared = sorted(v6_ids)

        gold_sub = [gold_by_id[s] for s in shared]
        coarse_sub = [coarse_by_id[s] for s in shared]
        v6_sub = subset_responses(v6, set(shared))
        pilot_sub = subset_responses(pilot, set(shared))

        def _eval(attempts: list[dict[str, Any]], gold_rows: list[dict[str, Any]]) -> dict[str, Any]:
            return evaluate_sun_literal_overlap(
                gold_rows, attempts, dataset_id=DATASET_ID, method_id=METHOD_ID
            )

        report: dict[str, Any] = {
            "schema_version": "d1_solcand_pilot_evaluation@1.0.0",
            "purpose": (
                "same-19-sample comparison: D1-R3 locked recipe (v6 prompt) vs "
                "Sol-candidate-semantics pilot (adapted historical Gold-candidate "
                "prompt), on fine and sentence-level coarse golds; fixed responses, "
                "no new LLM calls"
            ),
            "run_date_utc": "2026-08-07",
            "samples": shared,
            "arms": {
                "v6_baseline": {
                    "source": str(V6_BASELINE_RESPONSES),
                    "sha256": sha256_file(V6_BASELINE_RESPONSES),
                    "prompt": "direct_llm_sun_record_prompt_v6_d1r1_2026_08_05",
                    "note": "historical arm_b_v6_20260805c responses",
                },
                "solcand_pilot": {
                    "source": str(PILOT_RESPONSES),
                    "sha256": sha256_file(PILOT_RESPONSES),
                    "prompt": "direct_llm_sun_record_prompt_solcand_pilot_2026_08_07",
                    "manifest": str(PILOT_MANIFEST) if PILOT_MANIFEST.exists() else None,
                    "note": "adapted Gold-candidate semantics; development/attribution only",
                },
            },
            "golds": {
                "fine": {"semantic_sha256": fine_semantic, "spans": count_gold_spans(gold_sub)},
                "coarse_sentence": {"semantic_sha256": coarse_semantic, "spans": count_gold_spans(coarse_sub)},
            },
            "metrics": {
                "fine": {
                    "v6": _eval(v6_sub, gold_sub)["overall"],
                    "solcand": _eval(pilot_sub, gold_sub)["overall"],
                    "per_field_v6": {f: {k: v[k] for k in ("precision", "recall", "f1")} for f, v in _eval(v6_sub, gold_sub)["per_field"].items()},
                    "per_field_solcand": {f: {k: v[k] for k in ("precision", "recall", "f1")} for f, v in _eval(pilot_sub, gold_sub)["per_field"].items()},
                },
                "coarse_sentence": {
                    "v6": _eval(v6_sub, coarse_sub)["overall"],
                    "solcand": _eval(pilot_sub, coarse_sub)["overall"],
                    "per_field_v6": {f: {k: v[k] for k in ("precision", "recall", "f1")} for f, v in _eval(v6_sub, coarse_sub)["per_field"].items()},
                    "per_field_solcand": {f: {k: v[k] for k in ("precision", "recall", "f1")} for f, v in _eval(pilot_sub, coarse_sub)["per_field"].items()},
                },
            },
            "safety": {
                "gold": "audit_read_only",
                "llm_api": "not_called",
                "network": "not_called",
                "artifacts": "created_no_overwrite",
            },
        }

        report_path = output_dir / "solcand_pilot_evaluation.json"
        if report_path.exists():
            raise PilotError(f"refusing to overwrite: {report_path}")
        output_dir.mkdir(parents=True, exist_ok=True)
        with report_path.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(report, stream, ensure_ascii=False, indent=2)
            stream.write("\n")

    def _fmt(m: Mapping[str, Any]) -> str:
        return f"P {m['precision']:.4f} / R {m['recall']:.4f} / F1 {m['f1']:.4f}"

    print(
        json.dumps(
            {
                "samples": len(shared),
                "fine": {
                    "v6": _fmt(report["metrics"]["fine"]["v6"]),
                    "solcand": _fmt(report["metrics"]["fine"]["solcand"]),
                    "per_field_delta_f1": {
                        f: round(
                            report["metrics"]["fine"]["per_field_solcand"][f]["f1"]
                            - report["metrics"]["fine"]["per_field_v6"][f]["f1"],
                            4,
                        )
                        for f in FIELDS
                    },
                },
                "coarse_sentence": {
                    "v6": _fmt(report["metrics"]["coarse_sentence"]["v6"]),
                    "solcand": _fmt(report["metrics"]["coarse_sentence"]["solcand"]),
                    "per_field_delta_f1": {
                        f: round(
                            report["metrics"]["coarse_sentence"]["per_field_solcand"][f]["f1"]
                            - report["metrics"]["coarse_sentence"]["per_field_v6"][f]["f1"],
                            4,
                        )
                        for f in FIELDS
                    },
                },
                "report": str(report_path),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--source-commit", default=SOURCE_COMMIT)
    args = parser.parse_args()
    try:
        return run(args.output_dir, args.source_commit)
    except (PilotError, Estg150B0DevelopmentError, OSError, KeyError, TypeError, ValueError, subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        print(f"solcand pilot evaluation failed closed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
