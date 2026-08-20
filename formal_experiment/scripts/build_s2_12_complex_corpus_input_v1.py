# -*- coding: utf-8 -*-
"""Build/check the 36-record S2.12 Gold-blind formal input.

The committed input contains only fixed IDs, local source locators and
hashes.  It never imports or reads the S2.11 Gold, decisions, proposal, or
labels.  Third-party text is resolved locally only by later method runners.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MEMBERSHIP = ROOT / "outputs/reports/s2_11_corpus_membership_v1.json"
OUTPUT = ROOT / "data/input/s2_12_complex_corpus_formal_input_v1.json"
EXPECTED_MEMBERSHIP_SHA = (
    "a63c50ea3164e6629a66746531ad379c3970c8dfa86971eaa35186693bb7a2af"
)
FORBIDDEN_KEYS = {
    "text", "clauses", "modality", "actor", "action", "condition",
    "constraint", "exception", "actor_action_map", "order_relations",
    "decision", "gold",
}


class InputBuildFail(ValueError):
    """Fail-closed input build error."""


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def build_payload() -> dict[str, Any]:
    if _sha(MEMBERSHIP) != EXPECTED_MEMBERSHIP_SHA:
        raise InputBuildFail("S2.11 membership binding drift")
    membership = json.loads(MEMBERSHIP.read_text(encoding="utf-8"))
    if membership.get("record_count") != 40 or len(membership.get("quarantine", [])) != 4:
        raise InputBuildFail("membership must remain 40 inventory / 4 quarantine")
    members = membership.get("records")
    if not isinstance(members, dict) or len(members) != 36:
        raise InputBuildFail("membership must expose exactly 36 eligible records")

    records: list[dict[str, Any]] = []
    for sample_id in sorted(members):
        source = members[sample_id]
        parts = sample_id.split("/")
        if len(parts) != 3 or not parts[2].startswith("v"):
            raise InputBuildFail(f"bad sample locator: {sample_id}")
        try:
            version = int(parts[2][1:])
        except ValueError as exc:
            raise InputBuildFail(f"bad version locator: {sample_id}") from exc
        records.append({
            "sample_id": sample_id,
            "source": {
                "path": source["path"],
                "file_sha256": source["file_sha256"],
                "text_sha256": source["text_sha256"],
                "text_byte_size": source["text_byte_size"],
                "record_id": parts[1],
                "version": version,
            },
        })

    payload = {
        "schema_version": "s2_12_complex_corpus_input@1.0.0",
        "dataset_id": "s2_11_barrientos_complex_corpus_36_v1",
        "input_id": "s2_12_complex_corpus_formal_input_v1",
        "gold_blind": True,
        "record_count": 36,
        "source_policy": {
            "raw_text_committed": False,
            "runtime_resolution": (
                "resolve local source record only after verifying file and text SHA-256"
            ),
            "forbidden_payload_fields": [
                "text", "clauses", "modality", "actor", "action",
                "condition", "constraint", "exception", "actor_action_map",
                "order_relations", "decision", "gold",
            ],
        },
        "membership_binding": {
            "path": "outputs/reports/s2_11_corpus_membership_v1.json",
            "sha256": EXPECTED_MEMBERSHIP_SHA,
        },
        "records": records,
    }
    encoded = json.dumps(payload, ensure_ascii=False).lower()
    for key in FORBIDDEN_KEYS:
        # Exact JSON keys only; words inside the explicit forbidden list are allowed.
        if f'"{key}":' in encoded:
            raise InputBuildFail(f"Gold-blind input unexpectedly contains key {key!r}")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--publish", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()

    data = _json_bytes(build_payload())
    if args.check:
        if not OUTPUT.is_file() or OUTPUT.read_bytes() != data:
            raise InputBuildFail("committed Gold-blind input is missing or not byte-identical")
        print(f"S2.12 GOLD-BLIND INPUT VERIFIED records=36 sha256={hashlib.sha256(data).hexdigest()}")
        return 0
    if OUTPUT.exists():
        raise InputBuildFail(f"refusing to overwrite existing input: {OUTPUT}")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_bytes(data)
    print(f"S2.12 Gold-blind input published: {OUTPUT}")
    print(f"records=36 sha256={hashlib.sha256(data).hexdigest()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
