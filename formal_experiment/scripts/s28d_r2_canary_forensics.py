"""S2.8D-R2: Gold-blind offline span/offset forensics for the H1 canary.

Forensic-only, diagnostic-only.  Consumes the already-recorded sanitized
transport capture, the canary manifest, and the frozen B0 v10a artifact of
exactly one previously executed real canary call.  It never makes an API
call, never reads ``.env``, never reads Gold or Layer E, and never writes
back into any prediction.

What this script computes per rejected span:

* proposed start/end plus text lengths (UTF-8 bytes and code points) and
  SHA-256 -- never the text itself;
* ``source_text[start:end] == text`` strict slice check (the canonical
  contract);
* exact-occurrence analysis of the proposed text in the full source text
  and inside the original clause window (unique match / zero_match /
  ambiguous_match), with the unique candidate reanchor offsets when they
  exist;
* a conservative error classification with explicit evidence (never a
  guess).

It also emits two strict-bindable replay inputs:

* one ``--offline-transport-replay`` row whose ``response_body`` is a
  faithful reconstruction of the chat.completion envelope with the
  byte-identical captured ``message.content`` (the original raw body was
  never saved by design; its hash is recorded and cross-checked);
* one ``--offline-replay`` response carrying the diagnostic-only
  counterfactual envelope in which ONLY start/end values of spans with a
  unique exact clause-internal match are corrected.  If any rejected span
  lacks such a match the counterfactual fails closed (not written).

Deterministic: no timestamps, no random values; repeated runs are
byte-identical.  Overwriting existing outputs requires ``--overwrite``.

Safety declarations for the audit log:

* API calls = 0
* Gold read = no
* Layer E read = no
* real canary result is never modified
* counterfactual is diagnostic-only and is clearly labelled as such
* P/R = not_computed
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_SRC = _PROJECT_ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from bpc_hybrid.b0_artifact import (  # noqa: E402
    B0ArtifactError,
    load_b0_predictions,
    prediction_hash,
    read_json_values,
    sha256_file,
    verify_b0_manifest,
)
from bpc_hybrid.h1_transport import decode_chat_completion_envelope  # noqa: E402
from bpc_hybrid.prompt_loader import load_prompt  # noqa: E402

SPAN_FIELDS = ("actors", "actions", "conditions", "constraints", "exceptions")
EXPECTED_MODEL = "deepseek-v4-flash"
TRANSPORT_REPLAY_KEYS = (
    "request_id",
    "sample_id",
    "clause_id",
    "clause_index",
    "prompt_sha256",
    "prompt_variant",
    "b0_prediction_sha256",
    "response_body",
)
REPLAY_RESPONSE_KEYS = (
    "request_id",
    "sample_id",
    "clause_id",
    "clause_index",
    "prompt_sha256",
    "prompt_variant",
    "b0_prediction_sha256",
    "response_content",
)

_ASCII_RE = re.compile(r"^[\x00-\x7f]*$")
_EXTRA_SLICE_RE = re.compile(r"^[^\w]*$", re.UNICODE)


class ForensicsError(ValueError):
    """Fail-closed error for forensic input/binding violations."""


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_text(value: str) -> str:
    return _sha256_bytes(value.encode("utf-8"))


def _is_span(value: Any) -> bool:
    return (
        isinstance(value, Mapping)
        and isinstance(value.get("text"), str)
        and isinstance(value.get("start"), int)
        and isinstance(value.get("end"), int)
    )


def _occurrences(needle: str, haystack: str) -> list[int]:
    """All start indexes of exact substring occurrences (0-based)."""
    starts: list[int] = []
    index = haystack.find(needle)
    while index != -1:
        starts.append(index)
        index = haystack.find(needle, index + 1)
    return starts


def analyze_span(
    *,
    field_path: str,
    text: str,
    start: int,
    end: int,
    source_text: str,
    clause_span: Mapping[str, Any],
) -> dict[str, Any]:
    """One deterministic, text-free diagnostic row for a proposed span.

    ``field_path`` is a stable dotted path (e.g. ``modality.evidence[0]``,
    ``actors[0]``).  The output never contains the span text, the source
    text, or the clause text -- only hashes, lengths, offsets, and counts.
    """
    clause_start = int(clause_span.get("start", 0))
    clause_end = int(clause_span.get("end", len(source_text)))
    clause_window = source_text[clause_start:clause_end]
    text_bytes = text.encode("utf-8")
    extra_after = source_text[end : len(source_text)]

    row: dict[str, Any] = {
        "field_path": field_path,
        "proposed_start": start,
        "proposed_end": end,
        "proposed_text_utf8_length": len(text_bytes),
        "proposed_text_char_length": len(text),
        "proposed_text_sha256": _sha256_text(text),
        "source_text_sha256": _sha256_text(source_text),
        "source_text_utf8_length": len(source_text.encode("utf-8")),
        "source_text_char_length": len(source_text),
        "source_text_all_ascii": _ASCII_RE.fullmatch(source_text) is not None,
        "slice_matches": source_text[start:end] == text,
        "proposed_inside_clause_span": clause_start <= start and end <= clause_end,
        "full_source_occurrences": len(_occurrences(text, source_text)),
        "clause_window_occurrences": len(_occurrences(text, clause_window)),
    }

    full_starts = _occurrences(text, source_text)
    clause_starts = _occurrences(text, clause_window)
    if len(full_starts) == 1:
        row["full_source_unique_start"] = full_starts[0]
        row["full_source_unique_end"] = full_starts[0] + len(text)
    if len(clause_starts) == 1:
        row["clause_unique_start"] = clause_start + clause_starts[0]
        row["clause_unique_end"] = clause_start + clause_starts[0] + len(text)

    # ---- conservative error classification (evidence only) --------------
    codes: list[str] = []
    evidence: list[str] = []
    if row["slice_matches"]:
        codes.append("slice_ok")
        evidence.append("source_text[start:end] equals proposed text")
    elif len(full_starts) == 1:
        codes.append("correct_text_wrong_coordinates")
        ustart = full_starts[0]
        uend = full_starts[0] + len(text)
        evidence.append(
            f"proposed text has exactly one exact match in source_text "
            f"at [{ustart}:{uend}]"
        )
        if start != ustart:
            evidence.append(f"proposed start is {start - ustart:+d} vs unique match")
        if end != uend:
            evidence.append(f"proposed end is {end - uend:+d} vs unique match")
        if end > uend and _EXTRA_SLICE_RE.fullmatch(source_text[uend:end]):
            codes.append("boundary_punctuation_inclusion")
            evidence.append(
                f"proposed end extends {end - uend} chars over punctuation/space"
            )
        if row["full_source_occurrences"] != row["clause_window_occurrences"]:
            codes.append("frame_confusion_possible")
            evidence.append(
                "occurrence counts differ between full source_text and clause window"
            )
    elif len(full_starts) == 0:
        codes.append("zero_match")
        evidence.append("proposed text does not occur exactly in source_text")
    else:
        codes.append("ambiguous_match")
        evidence.append(
            f"proposed text occurs {len(full_starts)} times in source_text"
        )

    if not row["source_text_all_ascii"] and text_bytes and len(text_bytes) != len(text):
        codes.append("unicode_byte_confusion_possible")
        evidence.append("UTF-8 byte length differs from code-point length")
    row["classification_codes"] = codes
    row["classification_evidence"] = evidence
    row["extra_after_span_slice_char_length"] = len(extra_after)
    return row


def extract_patch_spans(envelope: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Flatten every span-bearing patch entry into ``(field_path, span)``."""
    spans: list[dict[str, Any]] = []
    patches = envelope.get("patches")
    if not isinstance(patches, Mapping):
        return spans
    modality = patches.get("modality")
    if isinstance(modality, Mapping):
        for ei, ev in enumerate(modality.get("evidence") or []):
            if _is_span(ev):
                spans.append(
                    {"field_path": f"modality.evidence[{ei}]", "span": dict(ev)}
                )
    for field_name in SPAN_FIELDS:
        items = patches.get(field_name)
        if not isinstance(items, list):
            continue
        for si, span in enumerate(items):
            if _is_span(span):
                spans.append(
                    {"field_path": f"{field_name}[{si}]", "span": dict(span)}
                )
    return spans


def rejection_codes_from_manifest(manifest: Mapping[str, Any]) -> dict[str, int]:
    """Rejection code counts recorded by the real canary run."""
    return dict(manifest.get("effective_patch", {}).get("rejection_reason_counts", {}))


def _span_text_of(error: str) -> str | None:
    """Extract the proposed span text quoted in a canonical rejection error.

    Canonical errors are formatted as
    ``clauses[0].actors[0] span text '<text>' does not match ...``.
    Returns None when the line has no quoted text (no guess is made).
    """
    match = re.search(r"span text '(.+)' does not match", error)
    if match is None:
        return None
    return match.group(1)


def collect_rejected_field_paths(errors: Iterable[str]) -> list[str]:
    """Field paths of span mismatches from the canonical rejection errors.

    Parses ``clauses[0].modality.evidence[0]``-style prefixes only; any
    line without a parseable prefix is ignored (never guessed).
    """
    paths: list[str] = []
    pattern = re.compile(r"^clauses\[0\]\.(\S+?) span text '")
    for error in errors:
        match = pattern.match(error)
        if match is not None:
            paths.append(match.group(1))
    return paths


def build_counterfactual_corrections(
    spans: Iterable[dict[str, Any]],
    source_text: str,
    clause_span: Mapping[str, Any],
) -> tuple[dict[str, tuple[int, int]] | None, dict[str, Any]]:
    """Corrections (start, end) for spans with a UNIQUE clause-internal match.

    Only the unique exact match inside the original clause window qualifies;
    every other span fails closed.  Returns ``(None, failures)`` when any
    rejected span cannot be reanchored, else ``(corrections, {})``.
    """
    clause_start = int(clause_span.get("start", 0))
    clause_end = int(clause_span.get("end", len(source_text)))
    clause_window = source_text[clause_start:clause_end]
    corrections: dict[str, tuple[int, int]] = {}
    failures: dict[str, str] = {}
    for item in spans:
        span = item["span"]
        path = item["field_path"]
        text = str(span.get("text", ""))
        if not text:
            failures[path] = "span text is empty; cannot reanchor"
            continue
        if source_text[int(span["start"]):int(span["end"])] == text:
            continue
        starts = _occurrences(text, clause_window)
        if len(starts) == 1:
            ustart = clause_start + starts[0]
            corrections[path] = (ustart, ustart + len(text))
        elif len(starts) == 0:
            failures[path] = "zero_match inside clause window; fail closed"
        else:
            failures[path] = (
                f"ambiguous_match inside clause window ({len(starts)} matches); "
                f"fail closed"
            )
    if failures:
        return None, failures
    return corrections, {}


def apply_corrections(envelope: Mapping[str, Any], corrections: Mapping[str, tuple[int, int]]) -> dict[str, Any]:
    """Return a deep copy of the envelope with ONLY start/end replaced.

    Text, IDs, fields, labels, and every other semantic value are never
    touched.  Field identity and ordering are preserved.
    """
    out = copy.deepcopy(dict(envelope))
    patches = out.get("patches")
    if not isinstance(patches, dict):
        return out
    for path, (ustart, uend) in corrections.items():
        if path.startswith("modality.evidence["):
            index = int(path[len("modality.evidence["):-1])
            modality = patches.get("modality")
            if isinstance(modality, dict):
                evidence = modality.get("evidence")
                if isinstance(evidence, list) and index < len(evidence) and _is_span(evidence[index]):
                    evidence[index]["start"] = ustart
                    evidence[index]["end"] = uend
            continue
        for field_name in SPAN_FIELDS:
            prefix = f"{field_name}["
            if not path.startswith(prefix):
                continue
            index = int(path[len(prefix):-1])
            items = patches.get(field_name)
            if isinstance(items, list) and index < len(items) and _is_span(items[index]):
                items[index]["start"] = ustart
                items[index]["end"] = uend
            break
    return out


def reconstruct_response_body(capture_row: Mapping[str, Any], content: str) -> str:
    """Reconstruct the chat.completion envelope body around the captured
    ``message.content`` (byte-identical to the captured content string).

    The original raw HTTP body was never saved (``raw_response_saved`` is
    false by design); only its SHA-256 is recorded.  This reconstruction is
    used exclusively for the offline strict replay through the SAME
    decoder/parser/validator/merge path.
    """
    body = {
        "id": capture_row.get("response_id"),
        "object": capture_row.get("response_object"),
        "model": (capture_row.get("models") or {}).get("returned"),
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": capture_row.get("finish_reason"),
            }
        ],
        "usage": dict(capture_row.get("usage") or {}),
    }
    return json.dumps(body, ensure_ascii=False)


def write_text_checked(path: Path, text: str, overwrite: bool) -> None:
    if path.exists() and not overwrite:
        raise ForensicsError(f"refusing to overwrite existing artifact: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    if temporary.exists():
        temporary.unlink()
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", type=Path, required=True)
    parser.add_argument("--canary-manifest", type=Path, required=True)
    parser.add_argument("--b0-predictions", type=Path, required=True)
    parser.add_argument("--b0-manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)

    try:
        capture_rows = read_json_values(args.capture)
        if len(capture_rows) != 1:
            print(
                f"Refusing to run: capture must contain exactly one row, "
                f"got {len(capture_rows)}."
            )
            return 2
        capture_row = capture_rows[0]

        canary_manifest = json.loads(args.canary_manifest.read_text(encoding="utf-8"))
        verify_b0_manifest(args.b0_predictions, args.b0_manifest)
        batch = load_b0_predictions(args.b0_predictions)
        records = {item.record["sample_id"]: item.record for item in batch}
    except (ForensicsError, B0ArtifactError, OSError, json.JSONDecodeError) as exc:
        print(f"Refusing to run: {exc}")
        return 2

    sample_id = str(capture_row.get("sample_id", ""))
    clause_id = str(capture_row.get("clause_id", ""))
    if sample_id not in records:
        print(f"Refusing to run: sample {sample_id!r} not found in B0 batch.")
        return 2
    record = records[sample_id]
    clause = next(
        (c for c in record.get("clauses", []) if c.get("clause_id") == clause_id),
        None,
    )
    if clause is None:
        print(f"Refusing to run: clause {clause_id!r} not found in B0 record.")
        return 2
    clause_span = clause.get("clause_span")
    if not _is_span(clause_span):
        print("Refusing to run: clause_span is not a valid span.")
        return 2
    source_text = str(record.get("source_text", ""))

    prompt_name = "rule_first_llm_fallback_masked_prompt"
    try:
        prompt = load_prompt(prompt_name)
    except Exception as exc:  # prompt_loader may raise FileNotFoundError etc.
        print(f"Refusing to run: cannot load prompt {prompt_name}: {exc}")
        return 2

    content = capture_row.get("sanitized_response_envelope", {}).get("content")
    if not isinstance(content, str) or not content:
        print("Refusing to run: capture envelope has no message.content.")
        return 2
    try:
        envelope = json.loads(content)
    except json.JSONDecodeError as exc:
        print(f"Refusing to run: captured content is not valid JSON: {exc}")
        return 2
    if not isinstance(envelope, dict):
        print("Refusing to run: captured content is not a JSON object.")
        return 2

    # ------------------------------------------------------------------
    # Binding verification (hash / request binding / identity / counts)
    # ------------------------------------------------------------------
    bindings: list[dict[str, Any]] = []
    checks: list[tuple[str, bool, str]] = []

    def check(name: str, ok: bool, detail: str) -> None:
        bindings.append({"check": name, "ok": bool(ok), "detail": detail})
        if not ok:
            checks.append((name, False, detail))

    check(
        "message_content_sha256",
        capture_row.get("message_content_sha256") == _sha256_text(content),
        "captured message.content SHA-256 matches its own hash",
    )
    check(
        "capture_file_sha256",
        canary_manifest.get("transport", {}).get("capture_sha256")
        == sha256_file(args.capture),
        "manifest transport.capture_sha256 equals the capture file hash",
    )
    check(
        "api_call_count",
        int(canary_manifest.get("llm_calls", -1)) == 1,
        "manifest llm_calls == 1 (user-authorized hard cap, no retry)",
    )
    check(
        "gate_false",
        canary_manifest.get("h1_non_identity_gate") is False,
        "manifest h1_non_identity_gate == false",
    )
    models = capture_row.get("models") or {}
    check(
        "model_identity",
        models.get("requested") == EXPECTED_MODEL
        and models.get("resolved") == EXPECTED_MODEL
        and models.get("returned") == EXPECTED_MODEL,
        "requested == resolved == provider-returned == deepseek-v4-flash",
    )
    check(
        "extraction_status",
        capture_row.get("extraction_status") == "ok_message_content"
        and capture_row.get("extraction_source") == "message.content"
        and capture_row.get("finish_reason") == "stop"
        and capture_row.get("response_object") == "chat.completion",
        "ok_message_content / stop / chat.completion",
    )
    check(
        "no_reasoning_no_tools",
        capture_row.get("reasoning", {}).get("present") is False
        and capture_row.get("tool_calls", {}).get("count") == 0,
        "reasoning absent, tool calls absent",
    )
    check(
        "b0_prediction_binding",
        capture_row.get("b0_prediction_sha256") == prediction_hash(record),
        "capture b0_prediction_sha256 equals B0 prediction hash",
    )
    check(
        "prompt_binding",
        capture_row.get("prompt_sha256") == prompt.sha256
        and capture_row.get("prompt_variant") == "masked_selected_v5",
        "capture prompt SHA equals the versioned masked v5 prompt",
    )
    check(
        "envelope_binding",
        envelope.get("sample_id") == sample_id
        and envelope.get("clause_id") == clause_id,
        "patch envelope sample_id/clause_id match the capture row",
    )
    usage = capture_row.get("usage") or {}
    check(
        "usage_recorded",
        usage.get("prompt_tokens") == 1305
        and usage.get("completion_tokens") == 436
        and usage.get("total_tokens") == 1741,
        "usage 1305/436/1741 as recorded",
    )
    rejection_counts = rejection_codes_from_manifest(canary_manifest)
    check(
        "rejection_codes",
        rejection_counts.get("canonical_invalid") == 1
        and rejection_counts.get("reference_mismatch") == 1,
        "manifest rejection codes canonical_invalid=1, reference_mismatch=1",
    )

    if any(not item['ok'] for item in bindings):
        print("Refusing to run: one or more binding checks failed.")
        for name, ok, detail in bindings:
            print(f"  [{('ok' if ok else 'FAIL')}] {name}: {detail}")
        return 2

    # ------------------------------------------------------------------
    # Per-span diagnostics
    # ------------------------------------------------------------------
    patch_spans = extract_patch_spans(envelope)
    span_diagnostics = [
        {
            **analyze_span(
                field_path=item["field_path"],
                text=str(item["span"]["text"]),
                start=int(item["span"]["start"]),
                end=int(item["span"]["end"]),
                source_text=source_text,
                clause_span=clause_span,
            ),
            "proposed_span_sha256": _sha256_text(str(item["span"]["text"])),
        }
        for item in patch_spans
    ]

    # Spans the real run rejected (from its own recorded errors) -- the
    # script cross-checks that its slice-based detection matches.
    manifest_events = canary_manifest.get("patch_events") or []
    rejection_errors: list[str] = []
    for event in manifest_events:
        if event.get("selected_for_call"):
            rejection_errors = list(event.get("rejection_reasons") or [])
            break
    recorded_paths = collect_rejected_field_paths(rejection_errors)
    rejected_spans = [
        row
        for row in span_diagnostics
        if not row["slice_matches"]
    ]
    detected_paths = sorted(row["field_path"] for row in rejected_spans)
    check(
        "rejected_span_matching",
        sorted(recorded_paths) == detected_paths,
        f"slice-detected rejected paths {detected_paths} == recorded "
        f"rejection paths {sorted(recorded_paths)}",
    )
    if not bindings[-1]["ok"]:
        print("Refusing to run: rejected-span cross-check failed.")
        return 2

    # ------------------------------------------------------------------
    # Diagnostic-only counterfactual (unique exact clause-internal match)
    # ------------------------------------------------------------------
    corrections, failures = build_counterfactual_corrections(
        patch_spans, source_text, clause_span
    )
    counterfactual: dict[str, Any] = {
        "diagnostic_only": True,
        "never_a_real_canary_result": True,
        "ready": corrections is not None,
        "rule": (
            "reanchor ONLY start/end to the unique exact match inside the "
            "original clause window; text/ids/fields/labels/relations untouched"
        ),
        "fail_closed_reasons": failures,
        "corrections": (
            {path: list(offset) for path, offset in corrections.items()}
            if corrections is not None
            else None
        ),
        "strict_result_preserved": True,
    }

    diagnostics = {
        "schema_version": "s28d_r2_forensics@1.0.0",
        "task": "S2.8D-R2",
        "analysis_type": "gold_blind_offline_forensics",
        "git_commit": None,
        "capture_sha256": sha256_file(args.capture),
        "canary_manifest_sha256": _sha256_bytes(
            args.canary_manifest.read_bytes()
        ),
        "sample_id": sample_id,
        "clause_id": clause_id,
        "clause_index": int(capture_row.get("clause_index", -1)),
        "model": models,
        "usage": usage,
        "message_content_sha256": capture_row.get("message_content_sha256"),
        "response_body_sha256_recorded": capture_row.get("response_body_sha256"),
        "raw_body_saved": False,
        "source_text_sha256": _sha256_text(source_text),
        "source_text_char_length": len(source_text),
        "clause_span": {"start": clause_span["start"], "end": clause_span["end"]},
        "prompt": {
            "name": prompt_name,
            "sha256": prompt.sha256,
            "variant": capture_row.get("prompt_variant"),
        },
        "rejection_reason_counts": rejection_counts,
        "bindings": bindings,
        "span_diagnostics": span_diagnostics,
        "counterfactual": counterfactual,
        "transport_replay": {
            "reconstruction": (
                "chat.completion envelope rebuilt around the byte-identical "
                "captured message.content; original raw body never saved"
            ),
            "decoder": "bpc_hybrid.h1_transport.decode_chat_completion_envelope",
        },
        "pr_f1": "not_computed",
    }

    transport_body = reconstruct_response_body(capture_row, content)
    transport_row = {
        "request_id": str(capture_row.get("request_id")),
        "sample_id": sample_id,
        "clause_id": clause_id,
        "clause_index": int(capture_row.get("clause_index", -1)),
        "prompt_sha256": str(capture_row.get("prompt_sha256")),
        "prompt_variant": str(capture_row.get("prompt_variant")),
        "b0_prediction_sha256": str(capture_row.get("b0_prediction_sha256")),
        "response_body": transport_body,
    }
    if set(transport_row) != set(TRANSPORT_REPLAY_KEYS):
        print("Internal error: transport replay row key mismatch.")
        return 2

    replay_artifacts: dict[str, Any] = {
        "transport_replay_row": {
            "name": "transport_replay_row.jsonl",
            "response_body_sha256": _sha256_text(transport_body),
            "decoded_status": decode_chat_completion_envelope(
                transport_body, "application/json"
            ).get("status"),
            "message_content_sha256": _sha256_text(content),
        }
    }

    output_dir = args.output_dir
    try:
        write_text_checked(
            output_dir / "diagnostics.json",
            json.dumps(diagnostics, indent=2, sort_keys=True, ensure_ascii=False)
            + "\n",
            args.overwrite,
        )
        write_text_checked(
            output_dir / "transport_replay_row.jsonl",
            json.dumps(transport_row, ensure_ascii=False) + "\n",
            args.overwrite,
        )
        if corrections is not None:
            counterfactual_envelope = apply_corrections(envelope, corrections)
            counterfactual_row = {
                "request_id": str(capture_row.get("request_id")),
                "sample_id": sample_id,
                "clause_id": clause_id,
                "clause_index": int(capture_row.get("clause_index", -1)),
                "prompt_sha256": str(capture_row.get("prompt_sha256")),
                "prompt_variant": str(capture_row.get("prompt_variant")),
                "b0_prediction_sha256": str(capture_row.get("b0_prediction_sha256")),
                "response_content": json.dumps(
                    counterfactual_envelope, ensure_ascii=False
                ),
            }
            if set(counterfactual_row) != set(REPLAY_RESPONSE_KEYS):
                print("Internal error: counterfactual response row key mismatch.")
                return 2
            write_text_checked(
                output_dir / "counterfactual_responses.jsonl",
                json.dumps(counterfactual_row, ensure_ascii=False) + "\n",
                args.overwrite,
            )
            replay_artifacts["counterfactual_responses"] = {
                "name": "counterfactual_responses.jsonl",
                "response_content_sha256": _sha256_text(
                    counterfactual_row["response_content"]
                ),
                "corrections": {
                    path: list(offset) for path, offset in corrections.items()
                },
            }
        else:
            replay_artifacts["counterfactual_responses"] = {
                "written": False,
                "fail_closed": True,
                "reasons": failures,
            }
    except ForensicsError as exc:
        print(f"Refusing to write: {exc}")
        return 2

    print(f"S2.8D-R2 forensics: sample={sample_id} clause={clause_id}")
    print(f"  spans analyzed: {len(span_diagnostics)}")
    print(f"  rejected spans: {len(rejected_spans)}")
    print(
        "  rejected paths: "
        + ", ".join(row["field_path"] for row in rejected_spans)
    )
    print(
        "  classification: "
        + "; ".join(
            f"{row['field_path']}={'+'.join(row['classification_codes'])}"
            for row in rejected_spans
        )
    )
    print(f"  counterfactual ready: {counterfactual['ready']}")
    if not counterfactual["ready"]:
        print(f"  counterfactual fail-closed reasons: {failures}")
    print(f"  diagnostics: {output_dir / 'diagnostics.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
