# -*- coding: utf-8 -*-
"""Group A Stage 2 for the SIM case: the project's locked non-LLM baseline (B0 v10a).

This replaces the earlier simplified deterministic adapter: group A must run the
same non-LLM method the project already published for the complex-corpus arm
(`sun_rule_only` / B0 v10a: CoreNLP + Tregex + locked BERT-TextCNN), invoked
through ``bpc_hybrid.estg150_b0_development_v10.run_b0_batch_v10`` exactly as the
GDPR pass-through arm does.

Language boundary (same disclosure as the GDPR arm): the locked modality
classifier was developed on a German contract; English sentences are passed
through the same slot, so this is a descriptive pass-through, not a
language-matched validation.

The output capsule is text-free (coordinates/labels only) and stays in the
gitignored development area.  Zero LLM/API; no Gold is read.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]

from bpc_hybrid import sim_case_c1 as core  # noqa: E402

RUN_DIR = ROOT / "outputs" / "development" / "sim_case_c1" / "stage2_baseline_v1"
DEFAULT_RUNTIME = Path("D:/environment/stanford-corenlp-4.5.10")


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def source_records() -> tuple[list[dict], dict]:
    requirements = core.load_requirements()
    records, texts = [], {}
    for rule_id in core.MAIN_RULES:
        text = requirements[(rule_id, 2)]
        sample_id = f"sim_{rule_id}_v2"
        texts[sample_id] = text
        records.append({"sample_id": sample_id, "approved_text_en": text,
                        "raw_text_de": text, "legacy_record_id": sample_id})
    return records, texts


def run(overwrite: bool, check_only: bool, runtime_home: Path, device: str) -> dict:
    from bpc_hybrid.estg150_b0_development_v10 import run_b0_batch_v10
    from bpc_hybrid.s2_12_method_adapter import adapt_method_attempts

    records, texts = source_records()
    plan = {
        "schema_version": "sim_case_c1_stage2_baseline_plan@1.0.0",
        "run_id": "sim_case_c1_stage2_baseline_v1",
        "method": "sun_rule_only (B0 v10a: CoreNLP + Tregex + locked BERT-TextCNN)",
        "entry_point": "bpc_hybrid.estg150_b0_development_v10.run_b0_batch_v10",
        "profile": "PROFILE_V10A",
        "runtime_home": str(runtime_home),
        "device": device,
        "sentences": [{"sample_id": r["sample_id"], "text_sha256": _sha(r["approved_text_en"]),
                       "text_length": len(r["approved_text_en"])} for r in records],
        "language_boundary": "English sentences passed through the German-contract classifier slot (descriptive)",
        "api_calls": 0,
        "gold_read": False,
    }
    if check_only:
        return {"status": "CHECK_OK", "plan": plan}

    (ROOT / ".tmp").mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="simc1-b0-", dir=ROOT / ".tmp") as raw_work:
        attempts, runtime = run_b0_batch_v10(ROOT, records, runtime_home=runtime_home,
                                             work_dir=Path(raw_work), device=device)
    adapted = adapt_method_attempts(attempts, "sun_rule_only")
    by_id = {row.get("sample_id"): row for row in adapted}
    missing = [r["sample_id"] for r in records if r["sample_id"] not in by_id]

    capsule = {
        "schema_version": "sim_case_c1_stage2_baseline@1.0.0",
        "run_id": plan["run_id"],
        "method_id": "sun_rule_only",
        "gold_read_by_runner": False,
        "record_count": len(by_id),
        "missing_sample_ids": missing,
        "records": [by_id[r["sample_id"]] for r in records if r["sample_id"] in by_id],
        "plan": plan,
        "runtime": {k: v for k, v in (runtime or {}).items() if isinstance(v, (str, int, float, bool))},
    }
    if check_only:
        return {"status": "CHECK_OK", "records": len(capsule["records"]), "missing": missing}

    outputs = {}
    for name, payload in (("plan.json", plan), ("capsule.json", capsule)):
        path = RUN_DIR / name
        if path.exists() and not overwrite:
            raise SystemExit(f"refusing to overwrite: {path}")
        path.parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps(payload, ensure_ascii=False, indent=1) + "\n"
        path.write_text(text, encoding="utf-8", newline="\n")
        outputs[name] = {"path": str(path.relative_to(core.REPO)).replace("\\", "/"),
                         "sha256": _sha(text), "bytes": len(text.encode("utf-8"))}
    return {"status": "BUILT", "records": len(capsule["records"]), "missing": missing,
            "outputs": outputs}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--overwrite", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--runtime-home", default=str(DEFAULT_RUNTIME))
    ap.add_argument("--device", default="cpu")
    args = ap.parse_args()
    result = run(overwrite=args.overwrite, check_only=args.check,
                 runtime_home=Path(args.runtime_home), device=args.device)
    print(json.dumps(result, ensure_ascii=False, indent=1)[:2500])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
