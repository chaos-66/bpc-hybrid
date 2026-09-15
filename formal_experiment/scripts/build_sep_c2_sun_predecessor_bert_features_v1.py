# -*- coding: utf-8 -*-
"""Extract a bounded chunk of frozen legal-BERT features for the clean probe.

Run one chunk per process so that CPU-only extraction stays comfortably below
interactive time limits.  The output is local-only, contains no sentence text,
and is ignored by Git.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import torch

FORMAL_ROOT = Path(__file__).resolve().parents[1]
SRC = FORMAL_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bpc_hybrid.sun_predecessors import bert_probe, common, dataset, evaluation  # noqa: E402

CACHE_REL = "outputs/development/sep_c2_sun_predecessors_v1/bert_features_v1"


def _split_texts(formal_root: Path, external_root: Path, split: str) -> tuple[list[str], list[str]]:
    if split in {"train", "dev", "official_test"}:
        splits = dataset.build_clean_splits(formal_root, external_root)
        rows = splits[split]
        return [str(row["sample_id"]) for row in rows], [str(row["text"]) for row in rows]
    if split == "estg150":
        rows = evaluation.load_formal_input(formal_root)
        return [str(row["sample_id"]) for row in rows], [str(row["raw_text_de"]) for row in rows]
    raise common.SunPredecessorError(f"unknown split: {split}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--formal-root", type=Path, default=FORMAL_ROOT)
    parser.add_argument("--external-data-root", type=Path, required=True)
    parser.add_argument("--split", required=True, choices=["train", "dev", "official_test", "estg150"])
    parser.add_argument("--start", type=int, required=True)
    parser.add_argument("--end", type=int, required=True)
    parser.add_argument("--max-length", type=int, default=192)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--cache-root", type=Path, default=None)
    args = parser.parse_args(argv)
    formal_root = Path(args.formal_root)
    cache_root = Path(args.cache_root) if args.cache_root else formal_root / CACHE_REL
    sample_ids, texts = _split_texts(formal_root, Path(args.external_data_root), args.split)
    if not (0 <= args.start < args.end <= len(texts)):
        raise common.SunPredecessorError(
            f"invalid chunk [{args.start}:{args.end}] for {args.split} of {len(texts)} rows"
        )
    if args.start >= args.end:
        raise common.SunPredecessorError("empty chunk")
    bundle = bert_probe.load_local_legal_bert(formal_root)
    chunk_texts = texts[args.start:args.end]
    chunk_ids = sample_ids[args.start:args.end]
    features = bert_probe.extract_features(
        bundle,
        chunk_texts,
        max_length=args.max_length,
        batch_size=args.batch_size,
    ).cpu().numpy().astype(np.float32)
    cache_root.mkdir(parents=True, exist_ok=True)
    stem = f"{args.split}_{args.start:05d}_{args.end:05d}"
    npz_path = cache_root / f"{stem}.npz"
    json_path = cache_root / f"{stem}.json"
    if npz_path.exists() or json_path.exists():
        raise common.SunPredecessorError(f"refusing to overwrite feature chunk: {stem}")
    np.savez_compressed(npz_path, features=features)
    text_hashes = [hashlib.sha256(text.encode("utf-8")).hexdigest() for text in chunk_texts]
    metadata = {
        "schema_version": "sep_c2_sun_predecessor_bert_feature_chunk@1.0.0",
        "split": args.split,
        "start": args.start,
        "end": args.end,
        "rows": len(chunk_ids),
        "sample_ids": chunk_ids,
        "text_sha256": hashlib.sha256(json.dumps(text_hashes).encode("ascii")).hexdigest(),
        "features_sha256": hashlib.sha256(features.tobytes()).hexdigest(),
        "feature_shape": list(features.shape),
        "encoder_revision": bundle.metadata["revision"],
        "feature_pooling": "attention-mask-aware mean of last_hidden_state",
        "max_length": args.max_length,
        "contains_raw_text": False,
        "local_only_do_not_commit": True,
    }
    json_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"WROTE {stem}: rows={len(chunk_ids)} features={features.shape} path={npz_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())