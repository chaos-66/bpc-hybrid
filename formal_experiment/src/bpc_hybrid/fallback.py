"""Mock LLM fallback interface and hybrid extraction (R6).

Provides the foundation for controlled LLM fallback **without** calling
any real LLM API.  R6 only implements:

* fallback trigger decision logic
* a mock fallback client (stub, deterministic)
* fallback schema validation
* a hybrid extractor that chains rule-first → trigger-check → mock-fallback

No network, no ``.env``, no API keys — this is pure infrastructure.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum, auto

from bpc_hybrid.extractor import extract_rule_first
from bpc_hybrid.normalization import repair_response_spans
from bpc_hybrid.schema import (
    ClauseExtraction,
    FieldSpan,
    MultiClauseExtractionResponse,
    SchemaValidationError,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_CONFIDENCE_THRESHOLD = 0.5

_SEMANTIC_FIELDS = ("modality", "actor", "action", "condition", "constraint", "exception")


# ---------------------------------------------------------------------------
# Custom exception
# ---------------------------------------------------------------------------

class FallbackError(ValueError):
    """Raised when the fallback path fails irrecoverably."""


# ---------------------------------------------------------------------------
# Decision reasons
# ---------------------------------------------------------------------------

class DecisionReason(Enum):
    """Why fallback was (or was not) triggered."""

    NO_FALLBACK_NEEDED = auto()
    MISSING_MODALITY = auto()
    MISSING_ACTOR = auto()
    MISSING_ACTION = auto()
    LOW_FIELD_CONFIDENCE = auto()
    LOW_CLAUSE_CONFIDENCE = auto()
    SCHEMA_VALIDATION_FAILURE = auto()
    FALLBACK_DISABLED = auto()


# ---------------------------------------------------------------------------
# Fallback decision
# ---------------------------------------------------------------------------

@dataclass
class FallbackDecision:
    """Result of the fallback trigger check."""

    should_trigger: bool
    """``True`` if the fallback path should be invoked."""

    reasons: list[DecisionReason] = field(default_factory=list)
    """One or more reasons explaining the decision."""

    def to_dict(self) -> dict:
        return {
            "should_trigger": self.should_trigger,
            "reasons": [r.name for r in self.reasons],
        }


# ---------------------------------------------------------------------------
# Fallback request / result
# ---------------------------------------------------------------------------

@dataclass
class FallbackRequest:
    """What the fallback client receives."""

    source_text: str
    source_id: str
    rule_response: MultiClauseExtractionResponse
    reasons: list[DecisionReason] = field(default_factory=list)


@dataclass
class FallbackResult:
    """What the fallback client returns."""

    response: MultiClauseExtractionResponse | None = None
    raw_dict: dict | None = None
    error: str | None = None

    @property
    def is_valid(self) -> bool:
        return self.response is not None and self.error is None


# ---------------------------------------------------------------------------
# Trigger logic
# ---------------------------------------------------------------------------

def _clause_is_normative(clause: ClauseExtraction) -> bool:
    """Heuristic: a clause is normative if it has a modality marker."""
    return clause.modality is not None


def should_trigger_fallback(
    response: MultiClauseExtractionResponse,
    *,
    field_confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
    clause_confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
) -> FallbackDecision:
    """Determine whether the rule-first output needs LLM fallback.

    Checks (in order):

    1. Schema validation — if the response is invalid, trigger.
    2. For each **normative** clause:
       a. Missing actor → trigger
       b. Missing action → trigger
       c. Any field confidence below *field_confidence_threshold* → trigger
       d. Whole clause confidence below *clause_confidence_threshold* → trigger

    Non-normative clauses (modality is ``None`` — e.g. definitions,
    warranties, legal consequences) are **not** checked for missing
    fields.
    """
    reasons: list[DecisionReason] = []

    # --- Schema validation ------------------------------------------------
    try:
        response.validate()
    except SchemaValidationError:
        reasons.append(DecisionReason.SCHEMA_VALIDATION_FAILURE)
        return FallbackDecision(should_trigger=True, reasons=reasons)

    # --- Per-clause checks ------------------------------------------------
    for clause in response.clauses:
        if not _clause_is_normative(clause):
            continue  # non-normative — skip missing-field checks

        if clause.actor is None:
            reasons.append(DecisionReason.MISSING_ACTOR)

        if clause.action is None:
            reasons.append(DecisionReason.MISSING_ACTION)

        # Check field-level confidences.
        for fname in _SEMANTIC_FIELDS:
            fs: FieldSpan | None = getattr(clause, fname)
            if fs is not None and fs.confidence < field_confidence_threshold:
                reasons.append(DecisionReason.LOW_FIELD_CONFIDENCE)
                break  # one per clause is enough

        # Clause-level confidence.
        if clause.confidence < clause_confidence_threshold:
            reasons.append(DecisionReason.LOW_CLAUSE_CONFIDENCE)

    if reasons:
        return FallbackDecision(should_trigger=True, reasons=reasons)

    return FallbackDecision(
        should_trigger=False,
        reasons=[DecisionReason.NO_FALLBACK_NEEDED],
    )


# ---------------------------------------------------------------------------
# Optional fallback trigger (R10.2.1 — independent of extract_hybrid)
# ---------------------------------------------------------------------------

_TRIGGER_REASON_EMPTY_RULE = "empty_rule_result"
_TRIGGER_REASON_CONTROLLED_SMOKE = "controlled_smoke"


def _should_trigger_optional_fallback(
    response: MultiClauseExtractionResponse,
    *,
    explicit_controlled_smoke: bool = False,
) -> tuple[bool, str | None]:
    """Determine whether the optional fallback path should be invoked.

    This function is **independent** of :func:`should_trigger_fallback`
    (which ``extract_hybrid`` depends on).  It adds empty-clause detection
    and explicit smoke support without changing the legacy strict path.

    Returns
    -------
    (should_trigger, reason_or_none)
    """
    # Controlled smoke gate (R10.3 readiness)
    if explicit_controlled_smoke:
        return True, _TRIGGER_REASON_CONTROLLED_SMOKE

    # Empty rule-first → trigger
    if len(response.clauses) == 0:
        return True, _TRIGGER_REASON_EMPTY_RULE

    # For non-empty responses, delegate to the existing shared trigger.
    decision = should_trigger_fallback(response)
    if decision.should_trigger:
        reason = ", ".join(r.name for r in decision.reasons)
        return True, reason

    return False, None


# ---------------------------------------------------------------------------
# Mock LLM fallback client
# ---------------------------------------------------------------------------

@dataclass
class MockLLMFallbackClient:
    """A stub fallback client that returns pre-configured responses.

    NEVER calls a real API.  No network, no ``.env``, no API keys.

    Parameters
    ----------
    fixed_response : MultiClauseExtractionResponse | None
        A fixed response to return for every ``complete()`` call.
        If ``None``, the client will raise :class:`FallbackError`
        (simulating an API failure).
    simulate_invalid : bool
        If *True*, return a raw dict that does **not** pass schema
        validation (used to test rejection of bad outputs).
    """

    fixed_response: MultiClauseExtractionResponse | None = None
    simulate_invalid: bool = False

    def complete(self, request: FallbackRequest) -> FallbackResult:
        """Return a mock fallback result for *request*.

        Does NOT access the network, ``.env``, or any API key.
        """
        if self.simulate_invalid:
            return FallbackResult(
                raw_dict={"schema_version": "0.1.0", "invalid": True},
                error="mock: simulated invalid response",
            )

        if self.fixed_response is None:
            return FallbackResult(
                error="mock: no fixed_response configured (simulates API failure)"
            )

        return FallbackResult(response=self.fixed_response)


# ---------------------------------------------------------------------------
# Hybrid extractor
# ---------------------------------------------------------------------------

def extract_hybrid(
    source_text: str,
    source_id: str = "synthetic",
    *,
    fallback_client: MockLLMFallbackClient | None = None,
    field_confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
    clause_confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
) -> MultiClauseExtractionResponse:
    """Run rule-first extraction, optionally fall back to a fallback client.

    The *fallback_client* must implement ``.complete(FallbackRequest) ->
    FallbackResult`` (duck-typed).  Compatible implementations include:

    * :class:`MockLLMFallbackClient` (R6 — in-process stub)
    * :class:`~bpc_hybrid.llm_client.LLMFallbackAdapter` (R7 — LLM bridge)

    Workflow
    --------
    1. ``extract_rule_first(source_text, source_id)``
    2. ``should_trigger_fallback(rule_response, ...)``
    3. If no fallback needed → return rule_response as-is.
    4. If fallback needed and *fallback_client* is provided:
       a. Call ``fallback_client.complete(...)``.
       b. Validate & repair the fallback result.
       c. Return the repaired response.
    5. If fallback needed but no *fallback_client* → raise
       :class:`FallbackError`.

    Raises
    ------
    FallbackError
        If fallback is needed but the client is ``None`` or the
        fallback output is invalid/unrepairable.
    """
    # Step 1 — rule-first
    rule_response = extract_rule_first(source_text, source_id=source_id)

    # Step 2 — trigger check
    decision = should_trigger_fallback(
        rule_response,
        field_confidence_threshold=field_confidence_threshold,
        clause_confidence_threshold=clause_confidence_threshold,
    )

    # Step 3 — no fallback needed
    if not decision.should_trigger:
        return rule_response

    # Step 4 — fallback needed
    if fallback_client is None:
        raise FallbackError(
            f"Fallback required (reasons: {[r.name for r in decision.reasons]}) "
            f"but no fallback_client provided"
        )

    request = FallbackRequest(
        source_text=source_text,
        source_id=source_id,
        rule_response=rule_response,
        reasons=decision.reasons,
    )

    result = fallback_client.complete(request)

    # Step 4b — validate & repair
    if not result.is_valid:
        raise FallbackError(
            f"Fallback failed: {result.error or 'unknown error'}"
        )

    # The fallback result must be a valid MultiClauseExtractionResponse.
    try:
        result.response.validate()  # type: ignore[union-attr]
    except SchemaValidationError as exc:
        raise FallbackError(
            f"Fallback response failed schema validation: {exc}"
        ) from exc

    # Repair spans.
    try:
        repaired = repair_response_spans(result.response)  # type: ignore[arg-type]
    except Exception as exc:
        raise FallbackError(
            f"Fallback span repair failed: {exc}"
        ) from exc

    return repaired


# ---------------------------------------------------------------------------
# Optional fallback integration (R10.2)
# ---------------------------------------------------------------------------

_FALLBACK_STATUS_DISABLED = "fallback_disabled"
_FALLBACK_STATUS_NOT_TRIGGERED = "fallback_not_triggered"
_FALLBACK_STATUS_MOCK_USED = "fallback_mock_used"
_FALLBACK_STATUS_SCHEMA_VALID = "fallback_schema_valid"
_FALLBACK_STATUS_SCHEMA_INVALID = "fallback_schema_invalid"
_FALLBACK_STATUS_NETWORK_ERROR_REDACTED = "fallback_network_error_redacted"
_FALLBACK_STATUS_CONFIG_MISSING = "fallback_config_missing"


@dataclass(frozen=True)
class OptionalFallbackResult:
    """Result wrapper for optional LLM fallback (R10.2).

    Holds the extraction response together with metadata describing
    whether and how the fallback path was exercised.  No provenance
    field is added to the schema — metadata lives only here.
    """

    response: MultiClauseExtractionResponse
    """The final extraction response (rule-first OR fallback output)."""

    fallback_status: str
    """One of the ``_FALLBACK_STATUS_*`` constants."""

    fallback_used: bool
    """``True`` only if fallback was triggered AND produced a valid
    schema-valid result that was accepted."""

    trigger_reason: str | None
    """Human-readable summary of trigger reason(s), or ``None``."""

    rule_first_preserved: bool
    """``True`` if the returned response is the rule-first result
    (fallback was not used, failed, or was rejected)."""


# ---------------------------------------------------------------------------
# Optional fallback helper
# ---------------------------------------------------------------------------

def extract_with_optional_llm_fallback(
    source_text: str,
    source_id: str = "synthetic",
    *,
    fallback_enabled: bool = False,
    fallback_client: MockLLMFallbackClient | None = None,
    field_confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
    clause_confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
    rule_first_extractor: Callable[
        [str, str], MultiClauseExtractionResponse
    ] | None = None,
    explicit_controlled_smoke: bool = False,
) -> OptionalFallbackResult:
    """Rule-first extraction with optional, conservative LLM fallback.

    Unlike :func:`extract_hybrid`, this function **never raises**
    due to fallback failure.  If the fallback path cannot produce a
    schema-valid result, the rule-first result is returned as-is.

    Parameters
    ----------
    source_text : str
        The regulatory sentence to extract.
    source_id : str
        Unique identifier for this extraction.
    fallback_enabled : bool
        If ``False`` (default), the fallback path is never consulted.
        Must be explicitly set to ``True`` by a gate.
    fallback_client:
        A duck-typed fallback provider implementing
        ``.complete(FallbackRequest) -> FallbackResult``.
        Compatible: :class:`MockLLMFallbackClient` (R6) and
        :class:`~bpc_hybrid.llm_client.LLMFallbackAdapter` (R7).
    field_confidence_threshold : float
        Passed to :func:`should_trigger_fallback` (non-empty path).
    clause_confidence_threshold : float
        Passed to :func:`should_trigger_fallback` (non-empty path).
    rule_first_extractor : Callable[[str, str], MultiClauseExtractionResponse] | None
        Test/mock injection hook.  If ``None``, defaults to
        :func:`extract_rule_first`.  Inject a fake extractor returning
        ``clauses=[]`` to test the empty-rule trigger path.
    explicit_controlled_smoke : bool
        If ``True``, forces fallback trigger regardless of rule-first
        output (R10.3 readiness hook, not for production benchmarks).

    Returns
    -------
    OptionalFallbackResult
        Always returns a valid result — never raises from the fallback
        path.

    Notes
    -----
    - No real API, no ``.env``, no network unless *fallback_client*
      is a real-API transport behind a gate.
    - No raw response is saved.
    - No secrets are logged.
    - No schema change to ``MultiClauseExtractionResponse``.
    """
    # ---- 1. Rule-first (always) ------------------------------------------
    _extract = rule_first_extractor or extract_rule_first
    rule_response = _extract(source_text, source_id)

    # ---- 2. Gate: fallback disabled --------------------------------------
    if not fallback_enabled:
        return OptionalFallbackResult(
            response=rule_response,
            fallback_status=_FALLBACK_STATUS_DISABLED,
            fallback_used=False,
            trigger_reason=None,
            rule_first_preserved=True,
        )

    # ---- 3. Gate: no fallback client -------------------------------------
    if fallback_client is None:
        return OptionalFallbackResult(
            response=rule_response,
            fallback_status=_FALLBACK_STATUS_CONFIG_MISSING,
            fallback_used=False,
            trigger_reason=None,
            rule_first_preserved=True,
        )

    # ---- 4. Trigger check ------------------------------------------------
    should_trigger, reason_str = _should_trigger_optional_fallback(
        rule_response,
        explicit_controlled_smoke=explicit_controlled_smoke,
    )

    if not should_trigger:
        return OptionalFallbackResult(
            response=rule_response,
            fallback_status=_FALLBACK_STATUS_NOT_TRIGGERED,
            fallback_used=False,
            trigger_reason=None,
            rule_first_preserved=True,
        )

    # ---- 5. Execute fallback ---------------------------------------------
    request = FallbackRequest(
        source_text=source_text,
        source_id=source_id,
        rule_response=rule_response,
        reasons=[],  # optional path does not require DecisionReason list
    )

    try:
        result = fallback_client.complete(request)
    except Exception:
        # Any exception from fallback → return rule-first
        return OptionalFallbackResult(
            response=rule_response,
            fallback_status=_FALLBACK_STATUS_NETWORK_ERROR_REDACTED,
            fallback_used=False,
            trigger_reason=reason_str,
            rule_first_preserved=True,
        )

    # ---- 6. Validate fallback result -------------------------------------
    if not result.is_valid or result.response is None:
        return OptionalFallbackResult(
            response=rule_response,
            fallback_status=_FALLBACK_STATUS_SCHEMA_INVALID,
            fallback_used=False,
            trigger_reason=reason_str,
            rule_first_preserved=True,
        )

    # Schema validation on the parsed response
    try:
        result.response.validate()
    except SchemaValidationError:
        return OptionalFallbackResult(
            response=rule_response,
            fallback_status=_FALLBACK_STATUS_SCHEMA_INVALID,
            fallback_used=False,
            trigger_reason=reason_str,
            rule_first_preserved=True,
        )

    # ---- 7. Accept valid fallback ----------------------------------------
    return OptionalFallbackResult(
        response=result.response,
        fallback_status=_FALLBACK_STATUS_SCHEMA_VALID,
        fallback_used=True,
        trigger_reason=reason_str,
        rule_first_preserved=False,
    )
