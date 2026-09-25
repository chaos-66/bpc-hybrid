# -*- coding: utf-8 -*-
"""Build the frozen R3 P2 model-side sidecar set (offline, no API)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for candidate in (ROOT / "src", ROOT / "scripts"):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from bpc_hybrid import stage1_label_semantics_p2 as p2  # noqa: E402
from bpc_hybrid.stage1_process import load_stage1_contract, parse_bpmn_file  # noqa: E402
from bpc_hybrid.stage3_r3_p2_adapter_v1 import (  # noqa: E402
    P2_CONFIG_PATH,
    build_model_sidecar,
    sha256_file,
)

INFERENCE_VIEW = ROOT / "data/development/stage3_reconstruction_v4/inference_view.json"
STRUCTURAL_CONTRACT = ROOT / "configs/stage1_structural_s11_s14.json"
DEFAULT_OUT_DIR = ROOT / "outputs/development/stage3_table3_r3_p2_sidecars"


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8", newline="\n")


def build(*, out_dir: Path = DEFAULT_OUT_DIR, case_ids: list[str] | None = None) -> dict:
    out_dir = Path(out_dir).resolve()
    import spacy  # type: ignore

    p2_config = p2.load_p2_config(P2_CONFIG_PATH)
    nlp = spacy.load("en_core_web_sm")
    contract = load_stage1_contract(STRUCTURAL_CONTRACT)
    view = _load_json(INFERENCE_VIEW)
    items = sorted(view.get("items") or [], key=lambda row: str(row["case_id"]))
    if case_ids:
        wanted = set(case_ids)
        items = [row for row in items if str(row["case_id"]) in wanted]
    if len(items) != 20 and not case_ids:
        raise RuntimeError(f"expected 20 inference items, got {len(items)}")

    out_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    runtime_seen = None
    for item in items:
        case_id = str(item["case_id"])
        bpmn_path = ROOT / str(item["bpmn_path"])
        record = parse_bpmn_file(bpmn_path, contract=contract)
        sidecar = build_model_sidecar(record, case_id=case_id, bpmn_path=bpmn_path,
                                      nlp=nlp, p2_config=p2_config)
        sidecar_path = out_dir / f"{case_id}.json"
        _write_json(sidecar_path, sidecar)
        runtime_seen = sidecar.get("p2_assets", {}).get("runtime") if runtime_seen is None else runtime_seen
        rows.append({
            "case_id": case_id,
            "bpmn_path": str(item["bpmn_path"]),
            "bpmn_sha256": sidecar["bpmn_sha256"],
            "process_record_sha256": sidecar["process_record_sha256"],
            "sidecar_path": sidecar_path.resolve().relative_to(ROOT.resolve()).as_posix(),
            "sidecar_sha256": sha256_file(sidecar_path),
            "node_count": len(sidecar.get("nodes") or []),
            "activity_count": sum(1 for n in sidecar.get("nodes") or [] if n.get("node_type") == "activity"),
            "event_count": sum(1 for n in sidecar.get("nodes") or [] if n.get("node_type") == "event"),
        })
    index = {
        "schema_version": "stage3_r3_p2_sidecar_index@1.0.0",
        "status": "complete",
        "source": "frozen P2 activity renderer + R3 named-event extension",
        "extension_note": (
            "The original P2 sidecar covered activities only. R3 extends the same "
            "frozen label analysis to named events. This is not a claim that the "
            "original P2 formal run covered the current 20 BPMN files."
        ),
        "p2_assets": {
            "code_path": Path(p2.__file__).relative_to(ROOT).as_posix(),
            "code_sha256": sha256_file(Path(p2.__file__)),
            "config_path": P2_CONFIG_PATH.relative_to(ROOT).as_posix(),
            "config_sha256": sha256_file(P2_CONFIG_PATH),
            "runtime": runtime_seen or {},
        },
        "counts": {
            "cases": len(rows),
            "nodes": sum(int(x["node_count"]) for x in rows),
            "activities": sum(int(x["activity_count"]) for x in rows),
            "events": sum(int(x["event_count"]) for x in rows),
        },
        "cases": rows,
    }
    index_path = out_dir / "index.json"
    index["index_path"] = index_path.resolve().relative_to(ROOT.resolve()).as_posix()
    _write_json(index_path, index)
    return index


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--case-id", action="append", default=None)
    args = parser.parse_args()
    index = build(out_dir=args.out_dir, case_ids=args.case_id)
    print(json.dumps({k: index.get(k) for k in ("status", "counts", "index_path")},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
