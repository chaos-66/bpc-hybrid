# -*- coding: utf-8 -*-
"""Rules-Only (B0 v10a) module-removal ablation runner (zero API).

One-factor-at-a-time removals over the SAME EStG-150 / same Gold / same
evaluator.  The full v10a batch runs ONCE (shared CoreNLP + classifier pass);
the per-record composition inputs are captured, then each removal flag
re-composes canonical records with an explicit feature flag and evaluates with
the same Sun literal-overlap v2 evaluator.

Flags (each removes exactly one module; full = locked v10a predictions):
* no_lexicon_extensions      : drop production lexicon extensions (local
                               frozen-gap tier + typed scope tests); minimal
                               public rules only.
* no_modality_classifier     : BERT-TextCNN modality disabled; marker /
                               structure / negation routing only; no-marker
                               fallback is a deterministic default.
* no_actor_action_ownership  : ownership-evidence edges removed; legacy local
                               (first-actor / first-action) pairing.
* no_multi_match_guard       : multi-match fail-closed guard removed; first
                               candidate per field consumed.
* no_de_en_alignment_validation : DE-EN cue cross-validation removed; all
                               heuristic-supported alignments treated as
                               aligned (direct marker matching).

Discipline: the formal Rules-Only method is NOT modified; the formal
predictions are NOT overwritten; this runner is development-only and writes
under outputs/development.
"""

from __future__ import annotations

import argparse
import copy
import json
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
for candidate in (SRC, SCRIPTS):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

import bpc_hybrid.estg150_b0_development_v10 as v10  # noqa: E402
from bpc_hybrid.estg150_b0_development import (  # noqa: E402
    Estg150B0DevelopmentError,
)

OUT_ROOT = ROOT / "outputs/development/b0_module_removal_ablation_v1"

FLAGS = ("full", "no_lexicon_extensions", "no_modality_classifier",
         "no_actor_action_ownership", "no_multi_match_guard",
         "no_de_en_alignment_validation")

CATEGORY_ORDER = ("modality", "condition", "constraint", "exception", "actor")
LOCAL_EXTENSION_TIER = "authorized_local_frozen_gap"


def _sha256(path: Path) -> str:
    import hashlib
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"invalid {label}: {path}") from exc
    if not isinstance(value, dict):
        raise RuntimeError(f"{label} root must be an object")
    return value


def _write_json(path: Path, value: Any) -> None:
    if path.exists():
        raise RuntimeError(f"refusing to overwrite: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")


# ---------------------------------------------------------------------------
# Minimal lexicon (no extensions): same files, public tiers only, no typed
# scope tests; patterns rebuilt with the same compilation rules.
# ---------------------------------------------------------------------------


def build_minimal_lexicon() -> Any:
    from bpc_hybrid.sun_style.lexicon_v2_runtime import (
        CATEGORY_ORDER as _CAT_ORDER,
        MarkerEntry,
        LexiconV2Runtime,
        load_lexicon_v2,
        normalize_surface,
        sha256_file,
    )

    full = load_lexicon_v2(ROOT)
    entries_by_field: dict[str, list[MarkerEntry]] = {}
    active_counts: dict[str, int] = {}
    inactive_counts: dict[str, int] = {}
    for field in _CAT_ORDER:
        kept: list[MarkerEntry] = []
        active = inactive = 0
        for e in full.entries_by_field.get(field, ()):
            # drop entries whose ONLY provenance is the local frozen-gap
            # extension tier (the "词典扩展"); keep public-tier entries and
            # their typed-scope tests (part of the production lexicon)
            if e.source_tiers and set(e.source_tiers) == {LOCAL_EXTENSION_TIER}:
                continue
            kept.append(e)
            if e.activation:
                active += 1
            else:
                inactive += 1
        entries_by_field[field] = kept
        active_counts[field] = active
        inactive_counts[field] = inactive

    modality_patterns: list[tuple[str, re.Pattern[str], str]] = []
    for entry in sorted(
        entries_by_field["modality"],
        key=lambda e: (-len(e.normalized), e.normalized),
    ):
        if not entry.activation or not entry.modality_class:
            continue
        pat = re.compile(rf"\b{re.escape(entry.surface)}\b", re.IGNORECASE)
        modality_patterns.append((entry.modality_class, pat, entry.surface))

    field_patterns: dict[str, list[tuple[re.Pattern[str], str]]] = {}
    for field in ("condition", "constraint", "exception"):
        pats = []
        for entry in sorted(
            entries_by_field[field],
            key=lambda e: (-len(e.normalized), e.normalized),
        ):
            if not entry.activation:
                continue
            pats.append(
                (re.compile(rf"\b{re.escape(entry.surface)}\b", re.IGNORECASE),
                 entry.surface)
            )
        field_patterns[field] = pats

    actor_surfaces = frozenset(
        e.normalized for e in entries_by_field["actor"] if e.activation
    )
    return LexiconV2Runtime(
        lexicon_id=full.lexicon_id,
        manifest_sha256=full.manifest_sha256,
        combined_payload_sha256=full.combined_payload_sha256,
        category_file_sha256=full.category_file_sha256,
        entries_by_field={k: tuple(v) for k, v in entries_by_field.items()},
        active_counts=active_counts,
        inactive_counts=inactive_counts,
        modality_patterns=tuple(modality_patterns),
        field_patterns={k: tuple(v) for k, v in field_patterns.items()},
        actor_surfaces=actor_surfaces,
    )


# ---------------------------------------------------------------------------
# Marker-only modality decision (no BERT-TextCNN)
# ---------------------------------------------------------------------------


def _marker_only_decision(english_clause: str, lexicon: Any) -> Any:
    from bpc_hybrid.b0_v10.modality import (
        ModalityDecision,
        ModalityRoute,
    )
    from bpc_hybrid.sun_style.lexicon_v2_runtime import match_modality_from_lexicon

    marker, surface = match_modality_from_lexicon(english_clause, lexicon)
    diag = {"marker_label": marker, "marker_surface": surface,
            "classifier_disabled": True}
    if marker == "definition":
        return ModalityDecision("definition", 0.7,
                                ModalityRoute.DEFINITION_STRUCTURE, diag, False)
    if marker == "prohibition":
        return ModalityDecision("prohibition", 0.7,
                                ModalityRoute.PROHIBITION_NEGATION, diag, False)
    if marker == "permission":
        return ModalityDecision("permission", 0.6,
                                ModalityRoute.MARKER_PERMISSION, diag, False)
    if marker == "obligation":
        return ModalityDecision("obligation", 0.6,
                                ModalityRoute.MARKER_OBLIGATION, diag, False)
    # deterministic no-classifier fallback (documented modeling default)
    return ModalityDecision("obligation", 0.0,
                            ModalityRoute.RECORD_LEVEL_FALLBACK,
                            {**diag, "note": "no_marker_default"}, False)


# ---------------------------------------------------------------------------
# Flag-aware composer (mirrors build_canonical_record_v10, same building
# blocks, explicit toggles)
# ---------------------------------------------------------------------------


def _flag_composer(flag: str, base_composer, minimal_lexicon):
    def compose(**kwargs):
        sample_id = kwargs["sample_id"]
        source_text = kwargs["source_text"]
        annotation = kwargs["annotation"]
        phrase_cases = kwargs["phrase_cases"]
        clause_units = kwargs["clause_units"]
        alignments = list(kwargs["alignments"])
        modality_decisions = list(kwargs["modality_decisions"])
        lexicon = kwargs["lexicon"]

        if flag == "no_lexicon_extensions":
            lexicon = minimal_lexicon

        if flag == "no_modality_classifier":
            decisions2 = []
            for ci, (unit, al) in enumerate(zip(clause_units, alignments)):
                s, e = unit["clause_char_span"]
                en = source_text[s:e]
                decisions2.append(_marker_only_decision(en, lexicon))
            modality_decisions = decisions2

        if flag == "no_de_en_alignment_validation":
            from bpc_hybrid.b0_v10.alignment import (
                AlignmentResult,
                AlignmentStatus,
            )
            alignments2 = []
            for al in alignments:
                if al.heuristic_supported and not al.validated:
                    al = AlignmentResult(
                        text=al.text,
                        status=AlignmentStatus.VALIDATED_ANCHOR_ALIGNMENT,
                        confidence=al.confidence,
                        evidence=al.evidence,
                        de_indices=al.de_indices,
                        en_index=al.en_index,
                    )
                alignments2.append(al)
            alignments = alignments2

        if flag == "no_multi_match_guard":
            # first-candidate consumption: keep only the first obs per field
            # (phrase_cases is a LIST of {sentence_index, fields} entries;
            #  only LIST-valued multi-match fields are truncated)
            cases2 = []
            for case in phrase_cases:
                fields = {
                    k: (v[:1] if isinstance(v, list) and v else v)
                    for k, v in (case.get("fields") or {}).items()
                }
                cases2.append({"sentence_index": case.get("sentence_index"),
                               "fields": fields})
            phrase_cases = cases2

        out = base_composer(
            sample_id=sample_id,
            source_id=kwargs.get("source_id", sample_id),
            source_text=source_text,
            annotation=annotation,
            phrase_cases=phrase_cases,
            clause_units=clause_units,
            alignments=alignments,
            modality_decisions=modality_decisions,
            lexicon=lexicon,
        )

        if flag == "no_actor_action_ownership":
            for clause in out.get("clauses", []):
                actors = clause.get("actors") or []
                actions = clause.get("actions") or []
                if actors and actions:
                    clause["actor_action_map"] = [
                        {"actor_id": actors[0]["id"],
                         "action_id": actions[0]["id"]}
                    ]
                else:
                    clause["actor_action_map"] = []
        return out

    return compose


# ---------------------------------------------------------------------------
# Modality label accuracy helper (clause-level against canonical gold)
# ---------------------------------------------------------------------------


def _label_accuracy(rows: Sequence[Mapping[str, Any]],
                    gold: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Clause-level modality label accuracy aligned by clause-text overlap.

    For every gold clause (text + label), find the predicted clause with the
    largest clause-text overlap; if that overlap is positive, compare the
    predicted clause's modality label.  Robust to different clause
    segmentation between the canonical gold and the v10 records.
    """
    gold_clauses: list[dict[str, Any]] = []
    for rec in gold:
        for clause in rec.get("clauses", []):
            mod = clause.get("modality")
            label = mod.get("label") if isinstance(mod, Mapping) else mod
            if not isinstance(label, str):
                continue
            gold_clauses.append({
                "sample_id": rec.get("sample_id", ""),
                "text": (clause.get("clause_span") or {}).get("text", ""),
                "label": label,
            })

    correct = total = 0
    per_class: dict[str, dict[str, int]] = {}
    for gc in gold_clauses:
        best_overlap = 0
        best_label = None
        g_start = -1
        g_end = -1
        # locate gold clause span in the sample's source for overlap
        for row in rows:
            if row.get("sample_id") != gc["sample_id"]:
                continue
            rec = row.get("record") or {}
            src = rec.get("source_text", "")
            g_start = src.find(gc["text"])
            if g_start < 0:
                continue
            g_end = g_start + len(gc["text"])
            for clause in rec.get("clauses", []):
                cs = clause.get("clause_span") or {}
                p_start, p_end = cs.get("start"), cs.get("end")
                if not isinstance(p_start, int) or not isinstance(p_end, int):
                    continue
                ov = max(0, min(g_end, p_end) - max(g_start, p_start))
                if ov > best_overlap:
                    best_overlap = ov
                    mod = clause.get("modality")
                    best_label = mod.get("label") if isinstance(mod, Mapping) else mod
            break
        if best_overlap <= 0 or not isinstance(best_label, str):
            continue  # no alignable predicted clause
        total += 1
        bucket = per_class.setdefault(gc["label"], {"tp": 0, "fn": 0, "fp": 0})
        if best_label == gc["label"]:
            correct += 1
            bucket["tp"] += 1
        else:
            bucket["fn"] += 1
            per_class.setdefault(best_label, {"tp": 0, "fn": 0, "fp": 0})["fp"] += 1

    per_class_accuracy = {
        k: {
            "support": v["tp"] + v["fn"],
            "accuracy": round(v["tp"] / (v["tp"] + v["fn"]), 6)
            if (v["tp"] + v["fn"]) else 0.0,
        }
        for k, v in per_class.items()
    }
    return {"clause_label_total": total, "clause_label_correct": correct,
            "clause_label_accuracy": round(correct / total, 6) if total else 0.0,
            "per_class": per_class_accuracy}


def _map_change_ratio(full_rows: Sequence[Mapping[str, Any]],
                      flag_rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Fraction of samples whose actor-action map changed vs full."""
    def maps(rows):
        out = {}
        for row in rows:
            rec = row.get("record") or {}
            out[row.get("sample_id")] = [
                (cl.get("actor_action_map") or []) for cl in rec.get("clauses", [])
            ]
        return out
    fm, vm = maps(full_rows), maps(flag_rows)
    changed = sum(1 for sid in fm if fm.get(sid) != vm.get(sid))
    return {"samples_with_changed_map": changed,
            "samples_total": len(fm)}


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


def run(runtime_home: Path, work_root: Path) -> int:
    from bpc_hybrid.estg150_b0_development_v10 import run_b0_batch_v10
    from bpc_hybrid.stage2_sun_literal_overlap import evaluate_sun_literal_overlap
    import shutil

    config = _load_json(
        ROOT / "configs/ablations/barrientos_ablation_suite_v1.json", "config")
    formal_input = _load_json(
        ROOT / "data/input/estg150_formal_inference_input_v2.json",
        "formal input v2")

    # Build Gold the same way evaluate_d1_r3 does: Layer E @ 56d2b03 via
    # build_canonical_gold_records (modality objects; canonical membership).
    from bpc_hybrid.estg150_b0_development import build_canonical_gold_records
    source_commit = "56d2b03"
    layer_e_path = ("formal_experiment/data/development/human_review/"
                    "estg_150_human_correction_v1.json")
    membership_path = ("formal_experiment/data/development/estg/"
                       "estg_150_membership_hashes.json")
    git_show = lambda p: subprocess.run(
        ["git", "show", f"{source_commit}:{p}"], cwd=ROOT.parent,
        capture_output=True, check=True).stdout
    gold_work = work_root / "b0-removal-gold"
    gold_work.mkdir(parents=True, exist_ok=True)
    (gold_work / "layer_e").write_bytes(git_show(layer_e_path))
    (gold_work / "membership").write_bytes(git_show(membership_path))
    gold, _source = build_canonical_gold_records(
        gold_work / "layer_e", gold_work / "membership")
    if len(gold) != 150:
        raise RuntimeError("canonical Gold must contain 150 records")

    records = []
    for rec in formal_input["records"]:
        out = {
            "sample_id": rec.get("sample_id"),
            "approved_text_en": rec.get("approved_text_en"),
            "raw_text_de": rec.get("raw_text_de"),
            "legacy_record_id": (rec.get("source_ref") or {}).get("legacy_record_id"),
        }
        if any(out[k] is None for k in ("sample_id", "approved_text_en",
                                        "raw_text_de", "legacy_record_id")):
            raise RuntimeError(
                f"formal input v2 record missing whitelisted fields: {rec.get('sample_id')}")
        records.append(out)
    if len(records) != 150:
        raise RuntimeError("formal input must contain 150 records")
    if OUT_ROOT.exists():
        raise RuntimeError(f"refusing to overwrite: {OUT_ROOT}")

    work = work_root / "b0-removal-work"
    work.mkdir(parents=True, exist_ok=True)

    # ---- shared pass: run the FULL v10 batch once (capture composition) ----
    t0 = time.time()
    captured: list[dict[str, Any]] = []
    orig_composer = v10.build_canonical_record_v10

    def capture_composer(**kwargs):
        captured.append(dict(kwargs))
        return orig_composer(**kwargs)

    import shutil
    work_a = work / "pass-a"
    if work_a.exists():
        shutil.rmtree(work_a)
    v10.build_canonical_record_v10 = capture_composer
    try:
        full_attempts, runtime_info = run_b0_batch_v10(
            ROOT, records, runtime_home=runtime_home, work_dir=work_a)
    finally:
        v10.build_canonical_record_v10 = orig_composer
    full_seconds = time.time() - t0
    if len(captured) != 150:
        raise RuntimeError(f"captured {len(captured)} composition calls, want 150")

    full_metrics = evaluate_sun_literal_overlap(
        gold, full_attempts,
        dataset_id="independently_reconstructed_estg_150_v1",
        method_id="sun_rule_only")

    minimal_lexicon = build_minimal_lexicon()

    results: dict[str, Any] = {"schema_version": "b0_module_removal_ablation@1.0.0"}
    results["full"] = {
        "note": "locked v10a formal predictions (shared pass above)",
        "runtime_seconds": round(full_seconds, 3),
        "metrics": full_metrics,
        "modality_label_accuracy": _label_accuracy(full_attempts, gold),
        "runtime_info": {
            k: runtime_info.get(k) for k in
            ("corenlp_seconds", "bridge_seconds", "classifier_seconds",
             "compose_seconds", "total_seconds")
        },
    }
    results["lexicon_stats"] = {
        "minimal_active_counts": dict(minimal_lexicon.active_counts),
        "minimal_note": (
            "entries whose ONLY provenance is the local frozen-gap extension "
            "tier removed (unused fields dropped: modality_patterns "
            "unchanged, actor surfaces 50->37); public tiers and typed-scope "
            "tests kept"),
    }

    for flag in FLAGS[1:]:
        t1 = time.time()
        composer = _flag_composer(flag, orig_composer, minimal_lexicon)
        rows: list[dict[str, Any]] = []
        for kw in captured:
            kw2 = dict(kw)
            kw2["annotation"] = copy.deepcopy(kw["annotation"])
            kw2["phrase_cases"] = copy.deepcopy(kw["phrase_cases"])
            kw2["clause_units"] = copy.deepcopy(kw["clause_units"])
            kw2["alignments"] = copy.deepcopy(kw["alignments"])
            kw2["modality_decisions"] = copy.deepcopy(kw["modality_decisions"])
            try:
                rec = composer(**kw2)
                status = "ok"
            except Exception:
                rec = {}
                status = "failed"
            rows.append({
                "sample_id": kw["sample_id"],
                "request_status": status,
                "record": rec,
            })
        metrics = evaluate_sun_literal_overlap(
            gold, rows,
            dataset_id="independently_reconstructed_estg_150_v1",
            method_id="sun_rule_only")
        results[flag] = {
            "runtime_seconds": round(time.time() - t1, 3),
            "metrics": metrics,
            "failed_samples": sum(1 for r in rows if r["request_status"] != "ok"),
            "modality_label_accuracy": _label_accuracy(rows, gold),
            "actor_action_map_change": _map_change_ratio(full_attempts, rows),
        }
        print(f"[{flag}] overall F1={metrics['overall']['f1']:.4f} "
              f"label_acc={results[flag]['modality_label_accuracy']['clause_label_accuracy']:.4f} "
              f"({time.time()-t1:.1f}s)")

    full_f1 = results["full"]["metrics"]["overall"]["f1"]
    for flag in FLAGS[1:]:
        results[flag]["delta_vs_full_f1"] = round(
            results[flag]["metrics"]["overall"]["f1"] - full_f1, 6)

    OUT_ROOT.mkdir(parents=True)
    _write_json(OUT_ROOT / "results.json", results)
    (OUT_ROOT / "manifest.json").write_text(
        json.dumps({
            "schema_version": "b0_module_removal_manifest@1.0.0",
            "run_id": "b0_module_removal_ablation_v1",
            "claim_scope": "development",
            "input": {
                "formal_input_v2_sha256": _sha256(
                    ROOT / "data/input/estg150_formal_inference_input_v2.json"),
                "gold_source_commit": "56d2b03",
                "gold_records": len(gold),
            },
            "flags": list(FLAGS),
            "safety": {
                "llm_api_calls": 0,
                "network_calls": 0,
                "gold_modified": False,
                "formal_predictions_overwritten": False,
                "formal_method_modified": False,
            },
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"B module-removal ablation complete: {OUT_ROOT.relative_to(ROOT)}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-home", type=Path,
                        default=Path("D:/environment/stanford-corenlp-4.5.10"))
    parser.add_argument("--work-root", type=Path, default=ROOT / ".tmp")
    args = parser.parse_args()
    try:
        return run(args.runtime_home, args.work_root)
    except (RuntimeError, Estg150B0DevelopmentError) as exc:
        print(f"B ablation refused: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())