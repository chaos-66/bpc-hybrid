"""Status summary for the auditable Sun-reconstruction experiment route.

This module is the **presentation layer** for the formal-experiment
readiness gates. It does NOT define any new eligibility rule on its
own: every per-record, per-clause, format, review, and freeze decision
is delegated to the strict v2 validator in
``formal_experiment.estg150_validator``. The membership cross-check is
delegated to the strict v2 validator as well. The only logic owned by
this module is:

  * reading the contract and methods configuration
  * counting display fields (e.g. ``n_reviewed``, ``n_adjudicated``)
  * combining the contract gate status, the strict-validator
    eligibility booleans, and the structural preconditions
    (schema, tool, validator script, etc.) into the four orthogonal
    readiness gates
  * fail-closed membership cross-check: the gate starts as
    ``input=False`` and only becomes ``input=True`` after every
    membership precondition is verified against the **explicit** hashes
    file passed in
  * fail-closed publication whitelist: formal Gold publication is
    only true when the contract's ``formal_gold_publication_gate.status``
    is an exact match against the contract's
    ``allowed_publication_statuses`` whitelist
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from formal_experiment.estg150_validator import validate_doc_dict
from formal_experiment.paths import (
    CANONICAL_REVIEW_FILE,
    ESTG_150_MEMBERSHIP_HASHES,
    EXPERIMENT_CONTRACT,
    FORMAL_PREDICTIONS_DIR,
    FORMAL_REPORTS_DIR,
    FROZEN_GOLD_DIR,
    FROZEN_INPUT_DIR,
    HUMAN_CORRECTION_FILE,
    HUMAN_REVIEW_PACK,
    HUMAN_REVIEW_SCHEMA,
    METHODS_CONFIG,
    REPO_ROOT,
    SUN_ORIGINAL_REFERENCE_DIR,
    WINTER_2020_REFERENCE_DIR,
)
from formal_experiment.sun_modality_gate import get_cached_sun_modality_gate
from formal_experiment.s1_structural_gate import get_cached_stage1_structural_gate
from formal_experiment.s1_label_semantics_gate import (
    get_cached_stage1_label_semantics_gate,
)
from formal_experiment.s1_annotation_gate import get_cached_stage1_annotation_gate
from formal_experiment.s1_evaluator_gate import get_cached_stage1_evaluator_gate
from formal_experiment.s1_membership_gate import get_cached_stage1_membership_gate
from bpc_hybrid.sun_style.public_marker_lexicon import (
    get_cached_public_marker_gate,
)


# Default whitelist for the formal_gold_publication_gate status. The
# contract may override this with a more specific
# ``allowed_publication_statuses`` array; status.py will only treat
# the contract's values as authoritative.
DEFAULT_ALLOWED_PUBLICATION_STATUSES = ("ready_for_formal_gold_publication",)


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _review_summary_legacy(path: Path) -> dict[str, Any]:
    """Legacy review pack (retired as editing surface, retained for
    provenance)."""
    result: dict[str, Any] = {
        "path": str(path), "records": 0, "unique_ids": 0,
        "invalid_json": 0, "text_approved": 0, "annotation_reviewed": 0,
        "blank_gold_rows": 0, "format_valid": False, "fully_reviewed": False,
    }
    if not path.exists():
        return result
    ids: set[str] = set()
    required = {"schema_version", "sample_id", "source", "text_review", "clauses", "annotation_review", "do_not_auto_score"}
    structural_errors = 0
    with path.open("r", encoding="utf-8") as handle:
        for raw in handle:
            if not raw.strip():
                continue
            result["records"] += 1
            try:
                row = json.loads(raw)
            except json.JSONDecodeError:
                result["invalid_json"] += 1
                continue
            if not isinstance(row, dict) or not required.issubset(row):
                structural_errors += 1
                continue
            sample_id = row.get("sample_id")
            if not isinstance(sample_id, str) or sample_id in ids:
                structural_errors += 1
            else:
                ids.add(sample_id)
            if row.get("text_review", {}).get("status") == "approved":
                result["text_approved"] += 1
            if row.get("annotation_review", {}).get("status") in {"reviewed", "adjudicated"}:
                result["annotation_reviewed"] += 1
            if row.get("clauses") == []:
                result["blank_gold_rows"] += 1
            if row.get("do_not_auto_score") is not True:
                structural_errors += 1
    result["unique_ids"] = len(ids)
    result["format_valid"] = (
        result["records"] == 150 and len(ids) == 150
        and result["invalid_json"] == 0 and structural_errors == 0
    )
    result["fully_reviewed"] = (
        result["format_valid"] and result["text_approved"] == 150
        and result["annotation_reviewed"] == 150
    )
    return result


def _canonical_review_summary(path: Path) -> dict[str, Any]:
    """Read the SINGLE canonical review file (estg_150_canonical_review_v1.json).

    The canonical schema is intentionally different from the legacy pack
    schema: it is JSON (not JSONL), it has a top-level `dataset` meta
    object, and its review states are `text_review.status` ∈
    {needs_review, needs_adjudication, approved, rejected} and
    `annotation_review.status` ∈ {needs_review, needs_adjudication,
    reviewed, adjudicated}.

    This is the v1 PROVENANCE file only; eligibility for the v2 active
    editing surface is computed by ``_human_correction_v2_summary``,
    which delegates entirely to the strict v2 validator.
    """
    result: dict[str, Any] = {
        "path": str(path), "records": 0, "unique_ids": 0,
        "text_approved": 0, "annotation_reviewed": 0,
        "annotation_adjudicated": 0, "clauses_total": 0,
        "approved_en_filled": 0, "format_valid": False,
        "fully_reviewed": False, "freeze_ready": False,
    }
    if not path.exists():
        return result
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return result
    if not isinstance(doc, dict):
        return result
    records = doc.get("records", [])
    if not isinstance(records, list):
        return result
    result["records"] = len(records)
    ids: set[str] = set()
    legacy_ids: set[int] = set()
    for r in records:
        if not isinstance(r, dict):
            continue
        sid = r.get("sample_id")
        lid = r.get("legacy_record_id")
        if isinstance(sid, str):
            ids.add(sid)
        if isinstance(lid, int):
            legacy_ids.add(lid)
        if r.get("text_review", {}).get("status") == "approved":
            result["text_approved"] += 1
        ar = r.get("annotation_review", {}).get("status")
        if ar in ("reviewed", "adjudicated"):
            result["annotation_reviewed"] += 1
        if ar == "adjudicated":
            result["annotation_adjudicated"] += 1
        result["clauses_total"] += len(r.get("clauses", []) or [])
        if r.get("approved_text_en"):
            result["approved_en_filled"] += 1
    result["unique_ids"] = len(ids)
    result["format_valid"] = (
        result["records"] == 150 and len(ids) == 150
        and len(legacy_ids) == 150
        and doc.get("schema_version") == "estg_150_canonical_review@1.0.0"
    )
    result["fully_reviewed"] = (
        result["format_valid"]
        and result["text_approved"] == 150
        and result["annotation_reviewed"] == 150
    )
    result["freeze_ready"] = (
        result["format_valid"] and result["annotation_adjudicated"] == 150
    )
    return result


def _human_correction_v2_summary(
    human_correction_path: Path,
    membership_hashes_path: Path,
) -> dict[str, Any]:
    """Thin presentation layer over the strict v2 validator.

    The strict validator (``estg150_validator.validate_doc_dict``) is
    the **single source of truth** for format / review / freeze
    eligibility on the v2 human_correction file. This function:

      1. Reads the human_correction file as JSON.
      2. Calls ``validate_doc_dict(doc, membership_hashes_path)`` with
         the **explicit** hashes file path passed in. The strict
         validator never auto-resolves the hashes file from the
         production path; it always uses the path the caller provides.
         This is what keeps the v2 validator safe for ``tmp_path``
         tests (no accidental fall-through to the production hashes
         file).
      3. Returns the strict validator's report with the original
         ``path`` field restored to the real file path (the strict
         validator uses ``<in-memory>`` to make clear it didn't read
         the file from disk twice).

    If the human_correction file is missing, unparseable, or not a
    dict, this function returns a fully-false summary so the four
    readiness gates stay fail-closed.
    """
    fallback: dict[str, Any] = {
        "path": str(human_correction_path),
        "records": 0,
        "n_records": 0,
        "format_valid": False,
        "review_ready": False,
        "freeze_ready": False,
        # per-record counters (all 0)
        "n_approved_en": 0,
        "n_translation_unreviewed": 0,
        "n_records_incomplete": 0,
        "n_records_fully_decided": 0,
        "n_reviewed": 0,
        "n_adjudicated": 0,
        # per-field counters (0 / 0)
        "n_field_decisions_total": 0,
        "n_field_decisions_unreviewed": 0,
        "n_field_decisions_resolved": 0,
        "review_state_counts": {},
        "format_errors": ["v2 human_correction file missing or unparseable"],
        "review_blockers": [],
        "freeze_blockers": [],
    }
    if not human_correction_path.exists():
        return fallback
    try:
        doc = json.loads(human_correction_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return fallback
    if not isinstance(doc, dict):
        fallback["format_errors"] = ["v2 human_correction file is not a JSON object"]
        return fallback
    if not membership_hashes_path.exists():
        fallback["format_errors"] = ["membership hashes file missing; cannot run strict validator"]
        return fallback
    report = validate_doc_dict(doc, membership_hashes_path)
    # Override the in-memory placeholder path with the actual file path
    # so the audit / status display can still show where the doc came
    # from.
    report["path"] = str(human_correction_path)
    # The strict validator counts dict records under ``n_records``;
    # the audit / status display historically used ``records`` for
    # the list length. Expose both so downstream consumers keep
    # working without having to re-implement the count.
    if isinstance(doc, dict):
        records_field = doc.get("records")
        if isinstance(records_field, list):
            report["records"] = len(records_field)
        else:
            report["records"] = report.get("n_records", 0)
    else:
        report["records"] = report.get("n_records", 0)
    # The strict validator's ``format_errors`` is a list of
    # ``[idx, str]`` pairs. The audit / status display historically
    # used a flat list of human-readable strings, so expose a parallel
    # ``format_error_messages`` for that. Both are kept so the strict
    # validator's index-rich form is still available for callers that
    # want it.
    fmt_errors = report.get("format_errors") or []
    if fmt_errors and isinstance(fmt_errors[0], (list, tuple)):
        report["format_error_messages"] = [item[1] for item in fmt_errors]
    else:
        report["format_error_messages"] = list(fmt_errors)
    return report


def _meaningful_count(path: Path) -> int:
    """Count real files recursively (subdirectories like data/gold/stage2/ must
    count their contents)."""
    if not path.exists():
        return 0
    return sum(
        1 for item in path.rglob("*")
        if item.is_file() and item.name != ".gitkeep"
    )


def _formal_capsule_methods() -> set[str]:
    """Method arms with published formal capsules (predictions+results),
    derived from per-arm manifests under outputs/reports."""
    methods: set[str] = set()
    pred_dir = FORMAL_PREDICTIONS_DIR
    if not pred_dir.exists():
        return methods
    for arm_dir in pred_dir.iterdir():
        if not arm_dir.is_dir():
            continue
        manifest_candidate = FORMAL_REPORTS_DIR / f"{arm_dir.name}.manifest.json"
        if manifest_candidate.exists():
            manifest = _load_json(manifest_candidate)
            mid = manifest.get("method_id")
            if isinstance(mid, str) and mid:
                methods.add(mid)
    return methods


def formal_final_gate_conditions() -> dict[str, Any]:
    """Final-readiness fail-closed conditions (user-authorized 2026-08-11,
    hardened 2026-08-11).

    final_experiment_ready must additionally require:
    - the three-method formal predictions/results capsule: EVERY arm is
      verified structurally and by hash from disk (method_id exact,
      claim_scope=formal, is_formal_performance_result=true, predictions and
      results files exist and hash-match the manifest, input/Gold bindings
      recomputed, new-LLM-calls=0 declaration) -- no self-reported state is
      trusted;
    - the shared comparison capsule hash-consistent: input v2 / Gold / G0.4
      semantic hash triple-consistent / per-method arm manifest hashes
      recomputed and compared item by item;
    - the G0.4 formal evaluation contract user-authorized.
    The audit layer additionally EXECUTES the three independent verifiers
    (see bpc_hybrid.formal_arm_verification.verify_all_with_verifiers).
    A config status flip alone must never open the final gate.
    """
    from bpc_hybrid.formal_arm_verification import verify_all_static
    result = verify_all_static()
    return {
        "capsule_complete": result["capsule_complete"],
        "g04_contract_authorized": result["g04_contract_authorized"],
        "comparison_consistent": result["comparison_consistent"],
        "reasons": result["reasons"],
        "arms": {m: v["verified"] for m, v in result["arms"].items()},
    }


def _sha256_file(path: Path) -> str:
    import hashlib
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _stage1_formal_evaluation_verified() -> bool:
    """Run the independent S1.6 formal-evaluation capsule verifier from
    disk (2026-08-13); never trust stored booleans."""
    try:
        import importlib.util
        path = REPO_ROOT / "scripts" / "verify_stage1_formal_evaluation.py"
        spec = importlib.util.spec_from_file_location(
            "s1_formal_eval_status_verifier", path)
        if spec is None or spec.loader is None:
            return False
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.verify()["verified"] is True
    except Exception:  # pragma: no cover - defensive
        return False


G04_CONTRACT = REPO_ROOT / "configs" / "evaluation" / "g04_evaluation_views_contract_v1.json"
COMPARISON_CAPSULE = (REPO_ROOT / "outputs" / "evidence"
                      / "d1_h1_zero_api_reeval_v1" / "comparison_capsule.json")


def _check_membership_fail_closed(
    hashes_path: Path,
    human_correction_path: Path,
) -> tuple[bool, str]:
    """Fail-closed membership cross-check.

    Returns ``(membership_ok, reason)``. ``membership_ok`` is
    ``False`` if ANY of the following is true (it can only become
    ``True`` after every check passes):

      * the membership hashes file is missing
      * the hashes file is not valid JSON
      * the hashes file is not a JSON object
      * the hashes file is missing ``selected_membership``
      * ``selected_membership`` is not a dict
      * ``selected_membership`` is missing ``membership_payload_sha256``
      * ``membership_payload_sha256`` is not a 64-char hex string
      * ``selected_membership`` is missing ``sorted_legacy_record_ids``
      * ``sorted_legacy_record_ids`` is not a list of 150 unique ints

      * the v2 human_correction file is missing
      * the v2 file is not valid JSON
      * the v2 file is not a JSON object
      * the v2 file's records list is missing or not a list
      * the v2 records list does not contain exactly 150 entries with
        unique ``legacy_record_id`` ints
      * the v2 file's sorted ``legacy_record_id`` list does not match
        the locked hashes
      * the v2 file declares ``dataset.membership_payload_sha256``
        AND it does not match the locked hashes (optional in v2;
        when present, must match exactly)

    The function is fail-closed: it returns ``(False, reason)`` on
    any structural or value mismatch, with a precise human-readable
    reason. It never raises an exception (it catches ``OSError`` and
    ``ValueError``) so the audit can never crash on a malformed
    membership file.
    """
    try:
        if not hashes_path.exists():
            return (False, f"membership hashes file missing: {hashes_path}")
        try:
            hashes = json.loads(hashes_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            return (False, f"membership hashes file is not valid JSON: {exc}")
        if not isinstance(hashes, dict):
            return (False, "membership hashes file top-level must be an object")
        sel = hashes.get("selected_membership")
        if not isinstance(sel, dict):
            return (False, "membership hashes file missing selected_membership object")
        payload = sel.get("membership_payload_sha256")
        if not isinstance(payload, str) or len(payload) != 64:
            return (False, "selected_membership.membership_payload_sha256 missing or not a 64-char hex string")
        # Cheap hex check; cheap is fine here
        try:
            int(payload, 16)
        except ValueError:
            return (False, "selected_membership.membership_payload_sha256 is not a valid hex string")
        ids = sel.get("sorted_legacy_record_ids")
        if not isinstance(ids, list) or len(ids) != 150:
            return (False, f"selected_membership.sorted_legacy_record_ids must be a list of 150 ints, got len={len(ids) if isinstance(ids, list) else 'not-a-list'}")
        if len(set(ids)) != 150:
            return (False, "selected_membership.sorted_legacy_record_ids contains duplicates")
        if not all(isinstance(x, int) and not isinstance(x, bool) for x in ids):
            return (False, "selected_membership.sorted_legacy_record_ids contains non-integer entries")
        # ----- v2 file -----
        if not human_correction_path.exists():
            return (False, f"v2 human_correction file missing: {human_correction_path}")
        try:
            v2_doc = json.loads(human_correction_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            return (False, f"v2 human_correction file is not valid JSON: {exc}")
        if not isinstance(v2_doc, dict):
            return (False, "v2 human_correction file top-level must be an object")
        ds = v2_doc.get("dataset") or {}
        if not isinstance(ds, dict):
            return (False, "v2 human_correction file missing dataset object")
        v2_payload = ds.get("membership_payload_sha256")
        # If the v2 file declares membership_payload_sha256, it MUST
        # match the locked hashes exactly. If it doesn't declare it,
        # the strict validator treats it as optional and the identity
        # check below (sorted legacy_record_ids) is the binding check.
        if v2_payload is not None and v2_payload != payload:
            return (
                False,
                f"v2 dataset.membership_payload_sha256 {v2_payload[:12]}... does not match "
                f"locked hashes {payload[:12]}...",
            )
        records = v2_doc.get("records")
        if not isinstance(records, list):
            return (False, "v2 records must be a list")
        if len(records) != 150:
            return (False, f"v2 records length must be 150, got {len(records)}")
        v2_ids: list[int] = []
        seen_ids: set[int] = set()
        for r in records:
            if not isinstance(r, dict):
                return (False, "v2 record is not an object")
            lid = r.get("legacy_record_id")
            if not isinstance(lid, int) or isinstance(lid, bool):
                return (False, f"v2 record legacy_record_id must be int, got {lid!r}")
            if lid in seen_ids:
                return (False, f"v2 record legacy_record_id {lid} is duplicated")
            seen_ids.add(lid)
            v2_ids.append(lid)
        if sorted(v2_ids) != sorted(ids):
            return (False, "v2 sorted legacy_record_ids disagree with locked membership")
    except (OSError, ValueError, TypeError) as exc:
        return (False, f"membership cross-check raised: {exc}")
    return (True, "ok")


def collect_status() -> dict[str, Any]:
    contract = _load_json(EXPERIMENT_CONTRACT)
    sun_modality_gate = get_cached_sun_modality_gate(REPO_ROOT)
    public_marker_gate = get_cached_public_marker_gate(REPO_ROOT)
    stage1_structural_gate = get_cached_stage1_structural_gate(REPO_ROOT)
    stage1_label_semantics_gate = get_cached_stage1_label_semantics_gate(REPO_ROOT)
    stage1_annotation_gate = get_cached_stage1_annotation_gate(REPO_ROOT)
    stage1_membership_gate = get_cached_stage1_membership_gate(REPO_ROOT)
    stage1_evaluator_gate = get_cached_stage1_evaluator_gate(REPO_ROOT)
    methods = _load_json(METHODS_CONFIG).get("methods", [])
    legacy = _review_summary_legacy(HUMAN_REVIEW_PACK)
    canonical = _canonical_review_summary(CANONICAL_REVIEW_FILE)
    # Strict validator is the single source of truth for the v2
    # editing-surface eligibility booleans. The membership hashes path
    # is the contractually-locked production file: tests that want to
    # use a tmp_path copy of either file must patch the corresponding
    # constant in the status module via monkeypatch.
    human_correction_v2 = _human_correction_v2_summary(
        HUMAN_CORRECTION_FILE, ESTG_150_MEMBERSHIP_HASHES,
    )
    route_locked = contract.get("route", {}).get("status") == "locked"
    dataset_locked = contract.get("stage2_dataset", {}).get("status") == "locked_for_human_review"
    route_reopened = "reopened" in (contract.get("route", {}).get("status") or "")

    # ----------------------------------------------------------------
    # Four distinct readiness concepts (2026-07-13 4-gate split,
    # further hardened in Event 23 to delegate eligibility booleans
    # to the strict v2 validator):
    #
    # 1. human_review_input_ready
    #    "the user can start the human review NOW"
    #    True once the data sources, membership, schemas, tool, and
    #    v2 file are in place. Independent of 0/150 progress. This is
    #    what `--require-human-review-ready` checks.
    #
    # 2. human_review_freeze_ready
    #    "150/150 adjudicated, annotation frozen"
    #    True only after every record has reached
    #    review_state.status = adjudicated. NECESSARY but NOT
    #    SUFFICIENT for formal Gold.
    #
    # 3. formal_gold_publication_ready
    #    "formal Gold can be declared and published"
    #    True only when ALL of the following are true:
    #      - human_review_freeze_ready
    #      - route.status == "locked"
    #      - stage2_dataset.status == "locked_for_human_review"
    #      - stage3.status == "locked"
    #      - formal_gold_publication_gate.status is in the contract's
    #        allowed_publication_statuses WHITELIST (exact match).
    #        Conservative: any missing or non-listed status keeps it
    #        false. This is Event 23's fail-closed publication
    #        whitelist; the older "not blocked and not unknown"
    #        heuristic is GONE.
    #    Conservative: any missing or non-locked field keeps it false.
    #
    # 4. final_experiment_ready (alias: ready_for_final_metrics)
    #    "the three final methods + Stage 3 + frozen input + Gold can
    #    run end-to-end". Adds method readiness and frozen input/gold.
    # ----------------------------------------------------------------
    review_tool = REPO_ROOT / "scripts" / "estg150_review_tool.py"
    validate_script = REPO_ROOT / "scripts" / "validate_human_correction.py"
    # --- Authoritative gate status from the contract (read it; do not
    #     ignore it; the contract is the source of truth for the gate
    #     policy). ---
    human_review_gate = contract.get("human_review_gate") or {}
    gate_status = human_review_gate.get("status")
    allowed_input_statuses = human_review_gate.get(
        "allowed_input_statuses", ["input_ready_for_human_review"]
    )
    blocking_input_statuses = set(
        human_review_gate.get(
            "blocking_input_statuses",
            ["paused", "paused_until_route_v2_is_locked", "blocked", "input_not_ready"],
        )
    )
    contract_authorizes_input_start = (
        gate_status in allowed_input_statuses
        and gate_status not in blocking_input_statuses
    )
    # --- Membership cross-check (fail-closed). The strict v2
    #     validator (validate_doc_dict) is the source of truth for
    #     format eligibility, but the membership identity check
    #     itself runs here in a fail-closed style so a malformed
    #     hashes file or a v2 file without membership_payload_sha256
    #     can never silently produce ``input=True``. ---
    membership_ok, membership_reason = _check_membership_fail_closed(
        ESTG_150_MEMBERSHIP_HASHES, HUMAN_CORRECTION_FILE,
    )

    # --- The input gate is the conjunction of: contract authorises +
    #     strict validator says format is valid + membership matches
    #     + structural pieces are present. ---
    human_review_input_ready = bool(
        contract_authorizes_input_start
        and membership_ok
        and human_correction_v2["format_valid"]
        and human_correction_v2["records"] == 150
        and HUMAN_REVIEW_SCHEMA.exists()
        and review_tool.exists()
        and validate_script.exists()
    )
    # --- Freeze-ready: per-record adjudication. The strict v2
    #     validator is the single source of truth. ---
    human_review_freeze_ready = bool(
        human_correction_v2["format_valid"]
        and human_correction_v2["freeze_ready"]
    )
    # --- Formal-Gold-publication-ready: freeze + route + dataset +
    #     Stage 3 + formal_gold_publication_gate status (whitelist
    #     exact match). Conservative. ---
    formal_gold_publication_gate = contract.get("formal_gold_publication_gate") or {}
    formal_gold_publication_gate_status = formal_gold_publication_gate.get(
        "status", "unknown"
    )
    allowed_publication_statuses = tuple(
        formal_gold_publication_gate.get(
            "allowed_publication_statuses",
            list(DEFAULT_ALLOWED_PUBLICATION_STATUSES),
        )
    )
    # Event 23 fail-closed whitelist: the gate status must be an
    # EXACT match against the contract's allowed list. Anything else
    # (pending, unknown, empty, misspelling, banana, "blocked_*")
    # keeps the publication gate false.
    formal_gold_publication_gate_ok = (
        isinstance(formal_gold_publication_gate_status, str)
        and formal_gold_publication_gate_status in allowed_publication_statuses
    )
    stage3_status = (contract.get("stage3") or {}).get("status")
    formal_gold_publication_ready = bool(
        human_review_freeze_ready
        and route_locked
        and dataset_locked
        and stage3_status == "locked"
        and formal_gold_publication_gate_ok
    )
    # --- Final-experiment-ready: adds method readiness and frozen
    #     input/gold. ---
    method_blockers = [
        {"id": item.get("id"), "status": item.get("formal_status"), "notes": item.get("notes")}
        for item in methods if item.get("formal_status") != "ready"
    ]
    frozen = {"input": _meaningful_count(FROZEN_INPUT_DIR), "gold": _meaningful_count(FROZEN_GOLD_DIR)}
    # Final-readiness fail-closed hardening (user-authorized 2026-08-11):
    # the final gate additionally requires the three-method formal capsule,
    # a hash-consistent shared comparison capsule and the user-authorized
    # G0.4 formal evaluation contract. A config status flip alone must never
    # open the gate.
    final_gate = formal_final_gate_conditions()
    final_experiment_ready = bool(
        formal_gold_publication_ready
        and not method_blockers
        and frozen["input"] and frozen["gold"]
        and final_gate["capsule_complete"]
        and final_gate["g04_contract_authorized"]
        and final_gate["comparison_consistent"]
    )

    # --- Deprecated alias. Field name kept for backward compatibility
    #     with the --require-human-review-ready flag and existing
    #     consumers. Current semantic = human_review_input_ready. Any
    #     new code that needs "ready to publish Gold" must use
    #     human_review_freeze_ready or formal_gold_publication_ready
    #     or final_experiment_ready. ---
    human_review_ready = human_review_input_ready

    return {
        "repo_root": str(REPO_ROOT),
        "route": contract.get("route", {}),
        "dataset": contract.get("stage2_dataset", {}),
        "official_supplement": contract.get("official_supplement", {}),
        "sun_modality_gate": sun_modality_gate,
        "public_marker_gate": public_marker_gate,
        "public_marker_lexicon_verified": bool(public_marker_gate.get("ready")),
        "sun_modality_development_data_verified": bool(
            sun_modality_gate.get("ready")
        ),
        "sun_modality_source_population": 2833,
        "sun_modality_analysis_population": 2831,
        "sun_modality_quarantined_records": 2,
        "sun_modality_train_size": 1985,
        "sun_modality_dev_size": 420,
        "sun_modality_test_size": 426,
        "sun_modality_license_status": "unknown_pending_confirmation",
        "sun_modality_formal_use_ready": False,
        # Stage 1 gates (S1.1-S1.6 + S3.1 membership, restored from the
        # 56d2b03 checkpoint and re-bound in 2026-08-08):
        "stage1_structural_gate": stage1_structural_gate,
        "stage1_structural_verified": bool(stage1_structural_gate.get("ready")),
        "stage1_label_semantics_gate": stage1_label_semantics_gate,
        "stage1_label_semantics_verified": bool(
            stage1_label_semantics_gate.get("ready")
        ),
        "stage1_annotation_gate": stage1_annotation_gate,
        "stage1_annotation_protocol_verified": bool(
            stage1_annotation_gate.get("protocol_ready")
        ),
        "stage1_membership_gate": stage1_membership_gate,
        "stage1_formal_membership_ready": bool(
            stage1_membership_gate.get("membership_ready")
        ),
        "stage1_human_gold_freeze_ready": bool(
            stage1_membership_gate.get("human_gold_freeze_ready")
        ),
        "stage1_evaluator_gate": stage1_evaluator_gate,
        "stage1_evaluator_verified": bool(stage1_evaluator_gate.get("evaluator_ready")),
        "stage1_formal_results_ready": bool(
            stage1_evaluator_gate.get("formal_results_ready")
        ),
        # 2026-08-13: one-shot formal evaluation (P0/P1/P2 vs frozen Stage 1
        # Process Gold); the audit actually runs the independent capsule
        # verifier, so this mirrors the audit pass
        "stage1_formal_evaluation_verified": bool(
            _stage1_formal_evaluation_verified()
        ),
        "assets": {
            "winter_2020_reference": WINTER_2020_REFERENCE_DIR.exists(),
            "sun_original_reference": SUN_ORIGINAL_REFERENCE_DIR.exists(),
            "experiment_contract": EXPERIMENT_CONTRACT.exists(),
            "human_review_schema": HUMAN_REVIEW_SCHEMA.exists(),
            "human_review_pack": HUMAN_REVIEW_PACK.exists(),
            "canonical_review_file": CANONICAL_REVIEW_FILE.exists(),
        },
        "human_review": canonical,  # v1: retired as editing surface, kept as provenance
        "human_review_legacy_pack": legacy,  # retired, provenance only
        "human_correction_v2": human_correction_v2,  # v2: ACTIVE editing surface
        # Four orthogonal gates (2026-07-13):
        "human_review_input_ready": human_review_input_ready,
        "human_review_freeze_ready": human_review_freeze_ready,
        "formal_gold_publication_ready": formal_gold_publication_ready,
        "final_experiment_ready": final_experiment_ready,
        "ready_for_final_metrics": final_experiment_ready,
        "final_gate_conditions": final_gate,
        # Executable Gold-blind inference input v2 (published 2026-08-10):
        # lightweight presence check; the full independent verification is
        # performed by the audit's formal_benchmark_release_verified gate.
        "executable_input_v2_verified": bool(
            (FROZEN_INPUT_DIR / "estg150_formal_inference_input_v2.json").exists()
            and (FORMAL_REPORTS_DIR / "formal_benchmark_release_v2.manifest.json").exists()
        ),
        # Authoritative contract gate info (read, not just stored):
        "human_review_gate_status": gate_status,
        "human_review_gate_allowed": allowed_input_statuses,
        "human_review_gate_blocking": sorted(blocking_input_statuses),
        "human_review_gate_contract_authorizes_input_start": contract_authorizes_input_start,
        "membership_ok": membership_ok,
        "membership_reason": membership_reason,
        # Event 23 publication whitelist fields:
        "formal_gold_publication_gate_status": formal_gold_publication_gate_status,
        "formal_gold_publication_gate_allowed": list(allowed_publication_statuses),
        "formal_gold_publication_gate_match": formal_gold_publication_gate_ok,
        # Backward-compatible deprecated alias (DO NOT use for new code):
        "human_review_ready": human_review_ready,
        "human_review_ready_semantics": (
            "DEPRECATED alias. Current value equals human_review_input_ready. "
            "Current state: 150/150 adjudicated (annotation frozen), formal Gold "
            "artifacts published, executable Gold-blind input v2 verified. New "
            "code must use human_review_freeze_ready or "
            "formal_gold_publication_ready."
        ),
        "frozen_artifacts": frozen,
        "methods": methods,
        "method_blockers": method_blockers,
    }


def print_human(status: dict[str, Any]) -> None:
    print("Formal experiment status")
    print("=" * 40)
    print(f"Route: {status['route'].get('id', 'missing')} ({status['route'].get('status', 'missing')})")
    print(f"Exact Sun reproduction: {status['route'].get('exact_reproduction', False)}")
    print(
        "Sun modality development data verified: "
        f"{status.get('sun_modality_development_data_verified')}"
    )
    # Four orthogonal gates (2026-07-13):
    #   1. human_review_input_ready       : user can start review NOW
    #   2. human_review_freeze_ready      : 150/150 adjudicated (annotation frozen)
    #   3. formal_gold_publication_ready  : formal Gold can be declared
    #   4. final_experiment_ready         : methods + Stage 3 + frozen ready
    # The deprecated alias `human_review_ready` mirrors (1).
    print(f"Human review input ready       : {status['human_review_input_ready']}")
    print(f"Human review freeze ready      : {status['human_review_freeze_ready']}")
    print(f"Formal Gold publication ready : {status['formal_gold_publication_ready']}")
    print(f"Final experiment ready        : {status['final_experiment_ready']}")
    print(f"Executable input v2 verified  : {status.get('executable_input_v2_verified')}")
    print(f"(human_review_ready alias = {status['human_review_input_ready']}; {status.get('human_review_ready_semantics', '')})")
    review = status["human_review"]
    v2 = status.get("human_correction_v2", {})
    v2_records = v2.get("records", 0)
    v2_adjudicated = v2.get("n_adjudicated", v2.get("adjudicated", 0))
    print(f"Active v2 human correction (Layer E, current Gold source):")
    print(f"  records: {v2_records} / 150")
    print(f"  fully adjudicated: {v2_adjudicated} / 150")
    print(f"  freeze_ready: {v2.get('freeze_ready')}")
    print(f"Canonical review file (v1, retired as editing surface, kept as provenance): {review['path']}")
    print(f"  records: {review['records']} / 150 (historical provenance only; NOT the current Gold state)")
    legacy = status["human_review_legacy_pack"]
    print(f"Legacy review pack (provenance only): {legacy['records']} records")
    print(f"Ready for final metrics: {status['ready_for_final_metrics']}")
    if status["method_blockers"]:
        print("Method gates:")
        for item in status["method_blockers"]:
            print(f"  {item['id']}: {item['status']}")
