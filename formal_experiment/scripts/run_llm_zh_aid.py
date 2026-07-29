"""Real LLM runner for the EStG-150 Layer D Chinese-aid workflow
(2026-07-14 hardened).

This script is the **only** code path authorized to call a real
LLM for Layer D. It is **fail-closed by default**: it refuses
to perform any LLM call unless the user explicitly passes
`--allow-llm`, a concrete `--provider`, `--model`, `--max-calls`,
and a sample range or `--run-id` (which is reused across pilot
and full runs).

Hard rules (see AGENTS.md, docs/AI_CHANGE_PROTOCOL.md, and
docs/LLM_BUDGET_PROPOSAL_2026-07-12.md):

  R1. **Default: do nothing.** Missing `--allow-llm` causes
      exit code 0 in dry-run mode. The runner NEVER calls any
      LLM without `--allow-llm`.
  R2. **Hard call cap.** `--max-calls N` is the upper bound on
      the number of LLM HTTP requests in one process. With at
      most 2 calls per sample, `max-calls=300` covers 150
      samples.
  R3. **Concrete model + provider.** `--model <name>` and
      `--provider <name>` are required and the model must not
      be the placeholder `annotation-only-default`.
  R4. **Sample range or manifest.** Either `--start-index N
      --end-index M` (a half-open index range over the
      150-sorted-sample list) or `--sample-manifest <path>` is
      required. For full runs the range MUST cover `[0, 150)`.
  R5. **Pilot mode.** `--pilot N` runs the first N samples of
      the current range and stops; the user must re-invoke the
      runner WITHOUT `--pilot`, the SAME `--run-id`, and the
      FULL range `[0, 150)` to continue.
  R6. **Single run_id for pilot+full.** The runner stores an
      immutable `run_config.json` per `run_id`. A resume with
      the same `run_id` MUST use the SAME provider / model /
      base_url / temperature / max_tokens / membership payload
      / Layer A/B/C / prompt A/B. Any mismatch is a HARD FAIL
      (no partial resume, no merging across different runs).
  R7. **Resume / chunk-and-resume.** Before each LLM call, the
      runner reads `<run_dir>/manifest.jsonl` and skips every
      sample_id that already has a `status=ok` row.
  R8. **Failure retry.** Up to 3 attempts per LLM call
      (exponential backoff 2/4/8 seconds). A sample that fails
      3 times is written into `<run_dir>/manifest.jsonl` with
      status=failed.
  R9. **Output target.** ALL output (manifest, v2 Layer D rows,
      run_config.json, run_summary.json) goes to
      `data/development/estg/llm_candidate_runs/<run_id>/`.
      The runner REFUSES to write to `data/input`, `data/gold`,
      `data/predictions`, `data/results`, or `outputs/reports`.
  R10. **Layer A/B/C/E untouched.** The runner never modifies
       `estg_selected_150_de.jsonl` (A),
       `estg_150_translation_en_v1.jsonl` (B),
       `estg_150_llm_six_element_candidates_v1.jsonl` (C), or
       `estg_150_human_correction_v1.json` (E). It only
       WRITES to the run_dir.
  R11. **API key safety.** The runner NEVER accepts the key as
       a command-line value. The key is read ONLY from
       (a) interactive hidden input (`getpass.getpass`), or
       (b) an environment variable whose NAME is supplied via
       `--api-key-env-name NAME`. The key is NEVER written to
       any output file, NEVER echoed in logs / exceptions /
       HTTP errors. The runner replaces the key with `***` in
       every place it is used.
  R12. **Call B is blind.** The runner constructs Call B's
       user-visible payload as `{sample_id, text_zh_from_call_a}`
       only. The runner REFUSES to include `text_de`,
       `candidate_text_en`, or any English six-element span
       string in the Call B payload. A runtime assertion checks
       the JSON-serialized payload for forbidden substrings.
  R13. **No parallel / no retry beyond 3.** No background jobs.
       No concurrent calls.
  R14. **OpenAI-compatible ONLY.** The runner implements a
       single OpenAI-compatible /chat/completions provider.
       Anthropic / Bedrock / Vertex / Azure are NOT supported
       in this build (they need their own adapters).

The runner exposes a **dry-run** mode (the default) that
performs every check above, plans the batch, prints the call
estimate, and exits 0 without calling any LLM. The
`--allow-llm` flag is the only way to opt into real calls.

Run from formal_experiment/:

    # dry-run
    python scripts/run_llm_zh_aid.py --help
    python scripts/run_llm_zh_aid.py \\
        --start-index 0 --end-index 3

    # pilot (uses the same --run-id as the full run)
    $RUN_ID = "run_20260714_layerd"
    python scripts/run_llm_zh_aid.py \\
        --allow-llm \\
        --provider openai_compatible \\
        --model <CONCRETE_MODEL> \\
        --base-url <CONCRETE_BASE_URL> \\
        --max-calls 6 \\
        --start-index 0 --end-index 3 \\
        --pilot 3 \\
        --run-id $RUN_ID

    # validate the pilot
    python scripts/validate_layer_d_v2.py \\
        --run-dir data/development/estg/llm_candidate_runs/$RUN_ID \\
        --allow-partial-pilot 3

    # continue with the same --run-id and the FULL range
    python scripts/run_llm_zh_aid.py \\
        --allow-llm \\
        --provider openai_compatible \\
        --model <CONCRETE_MODEL> \\
        --base-url <CONCRETE_BASE_URL> \\
        --max-calls 300 \\
        --start-index 0 --end-index 150 \\
        --run-id $RUN_ID

    # full 150 validation (no --allow-partial-pilot)
    python scripts/validate_layer_d_v2.py \\
        --run-dir data/development/estg/llm_candidate_runs/$RUN_ID

    # atomic promotion
    python scripts/promote_layer_d_v2.py \\
        --run-dir data/development/estg/llm_candidate_runs/$RUN_ID
"""
from __future__ import annotations

import argparse
import datetime
import getpass
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

# Reusable Layer D security + validator modules (2026-07-14).
from formal_experiment.layer_d_security import (
    BaseUrlValidationError, validate_base_url,
)  # noqa: E402


LAYER_A_PATH = REPO / "data" / "development" / "estg" / "estg_selected_150_de.jsonl"
LAYER_B_PATH = REPO / "data" / "development" / "human_review" / "estg_150_translation_en_v1.jsonl"
LAYER_C_PATH = REPO / "data" / "development" / "human_review" / "estg_150_llm_six_element_candidates_v1.jsonl"
LAYER_E_PATH = REPO / "data" / "development" / "human_review" / "estg_150_human_correction_v1.json"
LAYER_D_V1_PLACEHOLDER = REPO / "data" / "development" / "human_review" / "estg_150_review_aids_zh_v1.jsonl"
MEMBERSHIP_HASHES_PATH = REPO / "data" / "development" / "estg" / "estg_150_membership_hashes.json"

PROMPT_CALL_A_PATH = REPO / "prompts" / "zh_aid" / "zh_translation.md"
PROMPT_CALL_B_PATH = REPO / "prompts" / "zh_aid" / "en_back_translation.md"

LLM_CANDIDATE_RUNS_ROOT = REPO / "data" / "development" / "estg" / "llm_candidate_runs"

FORBIDDEN_OUTPUT_PREFIXES = (
    REPO / "data" / "input",
    REPO / "data" / "gold",
    REPO / "data" / "predictions",
    REPO / "data" / "results",
    REPO / "outputs" / "reports",
)

PLACEHOLDER_MODEL = "annotation-only-default"
SUPPORTED_PROVIDERS = ("openai_compatible",)

# Run-config immutability: these fields are baked into
# run_config.json on first creation and MUST match on resume.
# `base_url_sha256` is also locked so the runner refuses a
# resume against a typo'd or hostile base URL.
RUN_CONFIG_LOCKED_FIELDS = (
    "provider", "model", "base_url", "base_url_sha256", "temperature", "max_tokens",
    "thinking_mode",
    "membership_payload_sha256", "layer_a_sha256", "layer_b_sha256",
    "layer_c_sha256", "prompt_a_sha256", "prompt_b_sha256",
    "layer_e_sha256",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def sha256_path(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def now_utc() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def load_jsonl(path: Path) -> list[dict]:
    out: list[dict] = []
    if not path.exists():
        return out
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            out.append(json.loads(line))
    return out


def append_jsonl(path: Path, row: dict) -> None:
    """Append a single row to a JSONL file. The runner never
    embeds the API key in any row."""
    path.parent.mkdir(parents=True, exist_ok=True)
    # Defensive scrub: if any row somehow contains an "api_key"
    # or "Authorization" key, remove it before writing.
    scrubbed = {k: v for k, v in row.items()
                if k.lower() not in ("api_key", "authorization",
                                     "bearer", "x_api_key", "x-api-key")}
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(scrubbed, ensure_ascii=False) + "\n")


def normalize_v2_order(path: Path) -> None:
    """Atomically restore canonical Layer-A ordering after resume.

    Successful retry rows are appended, so a late retry would otherwise sit
    at EOF and fail the promotion ordering invariant. Duplicate sample IDs are
    refused rather than silently de-duplicated.
    """
    if not path.exists():
        return
    rows = load_jsonl(path)
    sample_ids = [row.get("sample_id") for row in rows]
    if len(sample_ids) != len(set(sample_ids)):
        raise RuntimeError(
            f"refusing to normalize {path}: duplicate sample_id rows detected"
        )
    rows.sort(key=lambda row: (
        int(row.get("legacy_record_id", 2**63 - 1)),
        str(row.get("sample_id", "")),
    ))
    tmp = path.with_suffix(
        path.suffix + f".{os.getpid()}.{time.time_ns()}.tmp"
    )
    tmp.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )
    os.replace(tmp, path)


def mask_api_key(k: str | None) -> str:
    if not k:
        return ""
    return "***"


def assert_safe_output_dir(out_dir: Path) -> None:
    out_dir = out_dir.resolve()
    for prefix in FORBIDDEN_OUTPUT_PREFIXES:
        prefix = prefix.resolve()
        try:
            out_dir.relative_to(prefix)
        except ValueError:
            continue
        raise SystemExit(
            f"ERROR: output dir {out_dir} is inside the forbidden prefix "
            f"{prefix}. The runner is not allowed to write to "
            f"data/input, data/gold, data/predictions, data/results, "
            f"or outputs/reports. Choose an output dir under "
            f"data/development/estg/llm_candidate_runs/<run_id>/."
        )


# ---------------------------------------------------------------------------
# API key acquisition (R11)
# ---------------------------------------------------------------------------
def acquire_api_key(env_name: str | None) -> str:
    """Read the API key from (a) the environment variable named
    `env_name`, or (b) interactive hidden input. NEVER accepts
    the key as a command-line value. NEVER logs the key.

    The order is: env var first (so scripts can be
    non-interactive), then interactive prompt.
    """
    if env_name:
        k = os.environ.get(env_name, "")
        if k:
            return k
        raise SystemExit(
            f"ERROR: --api-key-env-name={env_name!r} was given but the "
            f"environment variable is empty or unset. Either set the "
            f"variable, or omit --api-key-env-name to fall back to "
            f"interactive input."
        )
    # Interactive hidden prompt
    try:
        k = getpass.getpass("请输入 API key（输入不会显示）: ")
    except (EOFError, KeyboardInterrupt) as e:
        raise SystemExit(f"ERROR: API key input aborted: {e!r}")
    if not k:
        raise SystemExit("ERROR: empty API key. Refusing to call the LLM.")
    return k


# ---------------------------------------------------------------------------
# Sample indexing
# ---------------------------------------------------------------------------
def build_sample_index() -> list[dict]:
    de_rows = load_jsonl(LAYER_A_PATH)
    if len(de_rows) != 150:
        raise SystemExit(
            f"Layer A has {len(de_rows)} rows; expected 150. Refusing to run."
        )
    de_by_lid: dict[int, dict] = {}
    for r in de_rows:
        lid = r.get("id")
        if not isinstance(lid, int):
            raise SystemExit(f"Layer A row missing integer id: {r!r}")
        de_by_lid[lid] = r
    if not MEMBERSHIP_HASHES_PATH.exists():
        raise SystemExit(
            f"membership hashes file missing: {MEMBERSHIP_HASHES_PATH}"
        )
    hashes = json.loads(MEMBERSHIP_HASHES_PATH.read_text(encoding="utf-8"))
    sel = hashes.get("selected_membership") or {}
    expected_ids = sel.get("sorted_legacy_record_ids") or []
    if not isinstance(expected_ids, list) or len(expected_ids) != 150:
        raise SystemExit(
            f"membership hashes file does not declare 150 sorted_legacy_record_ids; "
            f"refusing to run."
        )
    if sorted(de_by_lid.keys()) != sorted(expected_ids):
        raise SystemExit(
            "Layer A legacy_record_ids do not match membership hashes; refusing to run."
        )
    out: list[dict] = []
    for lid in sorted(de_by_lid.keys()):
        sid = f"estg_{lid:06d}"
        out.append({
            "sample_id": sid,
            "legacy_record_id": lid,
            "raw_text_de": de_by_lid[lid].get("text", ""),
            "raw_text_de_sha256": sha256_text(de_by_lid[lid].get("text", "")),
        })
    return out


def resolve_sample_subset(
    index: list[dict],
    start_index: int | None,
    end_index: int | None,
    sample_manifest: Path | None,
) -> list[dict]:
    if sample_manifest is not None:
        if not sample_manifest.exists():
            raise SystemExit(f"--sample-manifest not found: {sample_manifest}")
        requested: list[str] = []
        with sample_manifest.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                obj = json.loads(line)
                if isinstance(obj, dict) and "sample_id" in obj:
                    requested.append(str(obj["sample_id"]))
                elif isinstance(obj, str):
                    requested.append(obj)
        wanted = set(requested)
        out = [r for r in index if r["sample_id"] in wanted]
        if len(out) != len(wanted):
            missing = wanted - {r["sample_id"] for r in out}
            raise SystemExit(
                f"--sample-manifest contains {len(missing)} sample_id(s) not in "
                f"the active 150: {sorted(missing)[:5]}..."
            )
        return out
    if start_index is None or end_index is None:
        raise SystemExit(
            "Either --sample-manifest OR both --start-index and --end-index "
            "must be provided."
        )
    if start_index < 0 or end_index < 0 or end_index <= start_index:
        raise SystemExit(
            f"Invalid index range: start={start_index}, end={end_index}. "
            f"Must satisfy 0 <= start < end <= {len(index)}."
        )
    if end_index > len(index):
        raise SystemExit(
            f"end_index={end_index} exceeds the 150-sample list (len={len(index)})."
        )
    return index[start_index:end_index]


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------
def read_system_prompt(p: Path) -> str:
    text = p.read_text(encoding="utf-8")
    marker = "## System Prompt"
    if marker not in text:
        raise SystemExit(f"system prompt marker missing in {p}")
    body = text[text.index(marker):]
    fence_start = body.find("```text")
    if fence_start < 0:
        fence_start = body.find("```")
    if fence_start < 0:
        raise SystemExit(f"no fenced system-prompt block in {p}")
    body = body[fence_start:]
    body = body[body.index("\n") + 1:]
    fence_end = body.find("```")
    if fence_end < 0:
        raise SystemExit(f"unterminated fenced system-prompt block in {p}")
    return body[:fence_end].strip()


def read_user_template(p: Path, marker: str) -> str:
    text = p.read_text(encoding="utf-8")
    if marker not in text:
        raise SystemExit(f"user template marker {marker!r} missing in {p}")
    user_block = text[text.index(marker):]
    cut = user_block.find("\n## ")
    if cut > 0:
        user_block = user_block[:cut]
    return user_block


def render_call_a(
    sample: dict,
    candidate_text_en: str,
    llm_six_element_candidate_en_json: str,
    user_template: str,
) -> str:
    out = user_template
    out = out.replace("{sample_id}", sample["sample_id"])
    out = out.replace("{legacy_id}", str(sample["legacy_record_id"]))
    out = out.replace("{text_de}", sample["raw_text_de"])
    out = out.replace("{candidate_text_en}", candidate_text_en)
    out = out.replace("{llm_six_element_candidate_en_json}",
                      llm_six_element_candidate_en_json)
    return out


def render_call_b(sample: dict, text_zh_from_call_a: str, user_template: str) -> str:
    out = user_template
    out = out.replace("{sample_id}", sample["sample_id"])
    out = out.replace("{text_zh_from_call_a}", text_zh_from_call_a)
    return out


# ---------------------------------------------------------------------------
# Call B blind-payload assertion (R12)
# ---------------------------------------------------------------------------
def assert_call_b_payload_is_clean(
    payload: str, sample: dict, candidate_text_en: str
) -> None:
    forbidden_substrings: list[str] = []
    if sample.get("raw_text_de"):
        forbidden_substrings.append(sample["raw_text_de"])
    if candidate_text_en:
        forbidden_substrings.append(candidate_text_en)
    for s in forbidden_substrings:
        if s in payload:
            raise SystemExit(
                f"FATAL: Call B payload for {sample['sample_id']!r} contains a "
                f"forbidden substring (length {len(s)}). Call B is a BLIND "
                f"back-translation and must never receive the German source or "
                f"the English candidate. The runner is aborting to keep the "
                f"experiment clean."
            )
    for marker in (
        "text_de:",
        "candidate_text_en:",
        "German source (authoritative",
    ):
        if marker in payload:
            raise SystemExit(
                f"FATAL: Call B payload for {sample['sample_id']!r} contains "
                f"the auxiliary-context marker {marker!r}. The runner is "
                f"aborting to keep Call B blind."
            )


# ---------------------------------------------------------------------------
# LLM HTTP call (R14: OpenAI-compatible ONLY)
# ---------------------------------------------------------------------------
def call_chat_completion(
    *,
    base_url: str,
    api_key: str,
    model: str,
    system_prompt: str,
    user_message: str,
    max_tokens: int,
    temperature: float,
    timeout_seconds: int,
    thinking_mode: str = "provider_default",
) -> dict:
    """Call an OpenAI-compatible /chat/completions endpoint.
    Returns the parsed JSON body, OR raises an exception.

    R11: the api_key appears ONLY in the HTTP Authorization
    header. It is NEVER printed, NEVER logged, NEVER written
    to a file, NEVER included in the raised exception message.
    """
    url = base_url.rstrip("/") + "/chat/completions"
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if thinking_mode not in ("provider_default", "enabled", "disabled"):
        raise ValueError(
            "thinking_mode must be one of: provider_default, enabled, disabled"
        )
    if thinking_mode != "provider_default":
        # DeepSeek V4 exposes the OpenAI-compatible extension
        # {"thinking": {"type": "enabled|disabled"}}.  Keep the field
        # opt-in so ordinary OpenAI-compatible providers never receive an
        # extension they may reject.
        body["thinking"] = {"type": thinking_mode}
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            # R11: the REAL api_key is sent in the Authorization
            # header. mask_api_key() returns the string "***"
            # and is used ONLY for stdout/stderr/file output.
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw)
    except urllib.error.HTTPError as e:
        try:
            err_body = e.read().decode("utf-8", errors="replace")
        except Exception:
            err_body = "<unreadable error body>"
        # R11: the api_key MUST NOT appear in the raised message.
        # We also scrub the err_body in case the server echoed
        # the Authorization header back.
        err_body_safe = err_body.replace(api_key, mask_api_key(api_key))
        raise RuntimeError(
            f"HTTP {e.code} from {url}: {err_body_safe[:500]} (api_key={mask_api_key(api_key)})"
        ) from e
    except urllib.error.URLError as e:
        # R11: api_key must not appear in the URL error message either.
        raise RuntimeError(f"URL error calling {url}: {e!r}") from e


def extract_assistant_text(chat_response: dict) -> str:
    try:
        return chat_response["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as e:
        raise RuntimeError(
            f"Could not extract assistant text from chat response: {e!r}; "
            f"response keys={list(chat_response.keys()) if isinstance(chat_response, dict) else type(chat_response).__name__}"
        )


def extract_token_usage(chat_response: dict) -> tuple[int, int]:
    usage = chat_response.get("usage") or {}
    return (
        int(usage.get("prompt_tokens", 0) or 0),
        int(usage.get("completion_tokens", 0) or 0),
    )


def extract_first_json_object(text: str) -> dict:
    s = text
    s = re.sub(r"^```(?:json)?\s*", "", s.strip())
    s = re.sub(r"\s*```$", "", s.strip())
    start = s.find("{")
    if start < 0:
        raise ValueError(f"no JSON object found in assistant text: {text[:200]!r}")
    depth = 0
    for i in range(start, len(s)):
        c = s[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                candidate = s[start:i + 1]
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError as e:
                    raise ValueError(
                        f"could not parse first JSON object: {e!r}; "
                        f"object={candidate[:200]!r}"
                    ) from e
    raise ValueError(f"unbalanced JSON object in assistant text: {text[:200]!r}")


# ---------------------------------------------------------------------------
# Sidecar lookups
# ---------------------------------------------------------------------------
def load_auxiliary_context() -> tuple[dict[str, str], dict[str, dict]]:
    b_rows = load_jsonl(LAYER_B_PATH)
    b_idx = {r["sample_id"]: r.get("candidate_text_en", "") for r in b_rows}
    c_rows = load_jsonl(LAYER_C_PATH)
    c_idx = {r["sample_id"]: r for r in c_rows}
    if len(b_idx) != 150:
        raise SystemExit(
            f"Layer B (EN candidate) has {len(b_idx)} unique sample_ids; "
            f"expected 150. Refusing to run."
        )
    if len(c_idx) != 150:
        raise SystemExit(
            f"Layer C (LLM six-element candidate) has {len(c_idx)} unique "
            f"sample_ids; expected 150. Refusing to run."
        )
    return b_idx, c_idx


def six_element_candidate_to_english_json(c_row: dict) -> str:
    clauses = c_row.get("clauses") or []
    out_clauses = []
    for c in clauses:
        fields = {}
        for fld in ("modality", "actor", "action", "condition", "constraint", "exception"):
            v = c.get(fld) or {}
            if isinstance(v, dict):
                fields[fld] = v.get("value")
            else:
                fields[fld] = v
        out_clauses.append({"clause_id": c.get("clause_id"), **fields})
    return json.dumps({"clauses": out_clauses}, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Run config immutability (R6)
# ---------------------------------------------------------------------------
def build_run_config(
    provider: str, model: str, base_url: str, temperature: float,
    max_tokens: int, run_id: str, expected_sample_count: int,
    expected_max_calls: int, thinking_mode: str = "provider_default",
) -> dict:
    hashes = json.loads(MEMBERSHIP_HASHES_PATH.read_text(encoding="utf-8"))
    return {
        "run_id": run_id,
        "provider": provider,
        "model": model,
        "base_url": base_url,
        "base_url_sha256": sha256_text(base_url),
        "temperature": temperature,
        "max_tokens": max_tokens,
        "thinking_mode": thinking_mode,
        "membership_payload_sha256": hashes["selected_membership"]["membership_payload_sha256"],
        "layer_a_sha256": sha256_path(LAYER_A_PATH),
        "layer_b_sha256": sha256_path(LAYER_B_PATH),
        "layer_c_sha256": sha256_path(LAYER_C_PATH),
        "prompt_a_sha256": sha256_path(PROMPT_CALL_A_PATH),
        "prompt_b_sha256": sha256_path(PROMPT_CALL_B_PATH),
        "layer_e_sha256": sha256_path(LAYER_E_PATH),
        "created_at_utc": now_utc(),
        "expected_sample_count": expected_sample_count,
        "expected_max_calls": expected_max_calls,
    }


def write_or_verify_run_config(run_dir: Path, new_cfg: dict) -> None:
    """Create run_config.json on first run; verify immutability on
    resume. Refuse resume on any mismatch."""
    cfg_path = run_dir / "run_config.json"
    if not cfg_path.exists():
        cfg_path.write_text(
            json.dumps(new_cfg, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return
    existing = json.loads(cfg_path.read_text(encoding="utf-8"))
    mismatches: list[str] = []
    for fld in RUN_CONFIG_LOCKED_FIELDS:
        if existing.get(fld) != new_cfg.get(fld):
            mismatches.append(
                f"{fld}: existing={existing.get(fld)!r}, new={new_cfg.get(fld)!r}"
            )
    if mismatches:
        raise SystemExit(
            f"FATAL: refusing to resume run_dir={run_dir} because the "
            f"run_config has drifted across runs. The run_config fields are "
            f"locked once written. Mismatched fields:\n  " +
            "\n  ".join(mismatches) +
            f"\nTo start a new run with a different model / provider / "
            f"prompt / membership, pick a NEW --run-id."
        )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument(
        "--allow-llm", action="store_true",
        help="REQUIRED to perform real LLM calls. Without this flag the runner "
             "is in dry-run mode: it checks everything, plans the batch, and "
             "exits 0 without calling any API.",
    )
    ap.add_argument(
        "--provider", type=str, default=None,
        choices=SUPPORTED_PROVIDERS,
        help=f"Provider identifier. Supported: {', '.join(SUPPORTED_PROVIDERS)}.",
    )
    ap.add_argument(
        "--model", type=str, default=None,
        help="Concrete model name (NOT 'annotation-only-default'). Required "
             "when --allow-llm is set.",
    )
    ap.add_argument(
        "--base-url", type=str, default="https://api.openai.com/v1",
        help="OpenAI-compatible base URL. Default: OpenAI public endpoint. "
             "Must be https:// for public hosts. http://localhost/127.0.0.1 "
             "requires --allow-insecure-localhost.",
    )
    ap.add_argument(
        "--allow-insecure-localhost", action="store_true",
        help="EXPLICIT opt-in to allow http://localhost or http://127.0.0.1 "
             "as base URLs. Use only for self-hosted OpenAI-compatible "
             "servers. Never use for public endpoints.",
    )
    ap.add_argument(
        "--max-calls", type=int, default=0,
        help="Hard upper bound on the number of LLM HTTP requests in this "
             "process. With at most 2 calls per sample, max-calls=300 covers "
             "the full 150. Required when --allow-llm is set.",
    )
    ap.add_argument("--start-index", type=int, default=None)
    ap.add_argument("--end-index", type=int, default=None)
    ap.add_argument(
        "--sample-manifest", type=Path, default=None,
        help="JSONL of {sample_id: ...} rows; an alternative to "
             "--start-index/--end-index. Sample_ids must be in the active 150.",
    )
    ap.add_argument(
        "--pilot", type=int, default=0,
        help="If > 0, run only the first N samples of the resolved range and "
             "stop. The user must re-invoke the runner WITHOUT --pilot, the "
             "SAME --run-id, and the FULL range [0, 150) to continue.",
    )
    ap.add_argument(
        "--api-key-env-name", type=str, default=None,
        help="Name of an environment variable that holds the API key. The "
             "runner reads the VALUE from the env var; it never accepts the "
             "key as a command-line value. If unset, the runner prompts "
             "interactively (hidden input) for the key.",
    )
    ap.add_argument("--max-tokens", type=int, default=2048)
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument(
        "--thinking-mode",
        choices=("provider_default", "enabled", "disabled"),
        default="provider_default",
        help="Optional OpenAI-compatible thinking extension. Use 'disabled' "
             "for DeepSeek V4 structured-output runs; the selected value is "
             "locked in run_config.json.",
    )
    ap.add_argument("--timeout-seconds", type=int, default=120)
    ap.add_argument(
        "--max-attempts", type=int, default=3,
        help="Max attempts per LLM call (default 3).",
    )
    ap.add_argument(
        "--run-id", type=str, default=None,
        help="Run identifier; must be unique per real run. Default: "
             "run_<UTC-timestamp>. The output dir is "
             "data/development/estg/llm_candidate_runs/<run_id>/.",
    )
    ap.add_argument(
        "--output-dir", type=Path, default=None,
        help="Override the output dir. Default: "
             "data/development/estg/llm_candidate_runs/<run_id>/.",
    )
    args = ap.parse_args()

    # --- Path safety ---
    if args.output_dir is not None:
        assert_safe_output_dir(args.output_dir)
    for required in (LAYER_A_PATH, LAYER_B_PATH, LAYER_C_PATH,
                     LAYER_D_V1_PLACEHOLDER, LAYER_E_PATH,
                     PROMPT_CALL_A_PATH, PROMPT_CALL_B_PATH,
                     MEMBERSHIP_HASHES_PATH):
        if not required.exists():
            raise SystemExit(f"required source file missing: {required}")
    # --- Dry-run mode ---
    if not args.allow_llm:
        print("[dry-run] no LLM call will be made; no API key requested.")
        print(f"  provider: {args.provider!r}")
        print(f"  model: {args.model!r}")
        print(f"  max-calls: {args.max_calls}")
        print(f"  range: start={args.start_index} end={args.end_index} "
              f"manifest={args.sample_manifest}")
        print(f"  pilot: {args.pilot}")
        print(f"  thinking-mode: {args.thinking_mode}")
        print(f"  run-id: {args.run_id}")
        print()
        try:
            index = build_sample_index()
            subset = resolve_sample_subset(
                index, args.start_index, args.end_index, args.sample_manifest
            )
        except SystemExit as e:
            print(f"  [dry-run] planning failed: {e}")
            return 2
        if args.pilot > 0:
            subset = subset[:args.pilot]
        n_samples = len(subset)
        n_calls_needed = n_samples * 2
        print(f"  planned samples: {n_samples}")
        print(f"  planned calls  : {n_calls_needed} (Call A + Call B per sample)")
        if args.max_calls > 0 and n_calls_needed > args.max_calls:
            print(f"  WARNING: n_calls_needed > max-calls={args.max_calls}; "
                  f"raise --max-calls or reduce the range.")
        print()
        print("To actually call the LLM, pass --allow-llm with --provider, "
              "--model, --max-calls, --run-id, and a sample range or manifest. "
              "The API key is read from the env var named by --api-key-env-name, "
              "or via hidden interactive prompt.")
        return 0
    # --- Real-run gates ---
    if args.provider is None:
        raise SystemExit(
            f"--provider is required when --allow-llm is set. "
            f"Supported: {', '.join(SUPPORTED_PROVIDERS)}."
        )
    if args.model is None or args.model.strip() == "":
        raise SystemExit("--model is required when --allow-llm is set.")
    if args.model == PLACEHOLDER_MODEL:
        raise SystemExit(
            f"--model {args.model!r} is the placeholder. Pass a concrete "
            f"model (e.g. llama-3.1-70b-instruct via a compatible endpoint, "
            f"gpt-4o-mini, claude-3-5-sonnet via a compatible proxy, etc.)."
        )
    if args.max_calls is None or args.max_calls <= 0:
        raise SystemExit("--max-calls is required and must be > 0.")
    if args.run_id is None or args.run_id.strip() == "":
        raise SystemExit(
            "--run-id is required when --allow-llm is set. Use the SAME "
            "--run-id for the pilot and the full run; the runner refuses to "
            "merge two different run_ids."
        )
    # --- Base URL security (S1-S5) ---
    try:
        args.base_url = validate_base_url(
            args.base_url,
            allow_insecure_localhost=args.allow_insecure_localhost,
        )
    except BaseUrlValidationError as e:
        raise SystemExit(
            f"ERROR: --base-url validation failed: {e!r}. "
            f"Use https:// for public endpoints; pass "
            f"--allow-insecure-localhost only for self-hosted "
            f"http://localhost / http://127.0.0.1 servers."
        )
    # --- Build sample index and subset ---
    index = build_sample_index()
    subset = resolve_sample_subset(index, args.start_index, args.end_index, args.sample_manifest)
    if args.pilot > 0:
        subset = subset[:args.pilot]
        print(f"[pilot mode] running first {len(subset)} samples of the resolved range")
    n_samples = len(subset)
    n_calls_needed = n_samples * 2
    if n_calls_needed > args.max_calls:
        raise SystemExit(
            f"Requested {n_samples} samples * 2 calls = {n_calls_needed} calls, "
            f"which exceeds --max-calls={args.max_calls}. Reduce the range or "
            f"raise --max-calls."
        )
    print(f"[real-run] {n_samples} samples, {n_calls_needed} LLM calls "
          f"(max-calls={args.max_calls})")
    print(f"[real-run] provider={args.provider} model={args.model!r} base_url={args.base_url}")
    # --- Run dir ---
    run_id = args.run_id
    if args.output_dir is not None:
        run_dir = args.output_dir
    else:
        run_dir = LLM_CANDIDATE_RUNS_ROOT / run_id
    assert_safe_output_dir(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    print(f"[real-run] run_id={run_id} run_dir={run_dir}")
    # --- Build / verify run_config.json (R6) ---
    new_run_cfg = build_run_config(
        provider=args.provider, model=args.model, base_url=args.base_url,
        temperature=args.temperature, max_tokens=args.max_tokens,
        run_id=run_id, expected_sample_count=150, expected_max_calls=300,
        thinking_mode=args.thinking_mode,
    )
    write_or_verify_run_config(run_dir, new_run_cfg)
    print(f"[run_config] locked: provider={args.provider} model={args.model!r}")
    # --- API key (R11) ---
    api_key = acquire_api_key(args.api_key_env_name)
    # --- Sidecar lookups + prompts ---
    b_idx, c_idx = load_auxiliary_context()
    prompt_a_sha = sha256_path(PROMPT_CALL_A_PATH)
    prompt_b_sha = sha256_path(PROMPT_CALL_B_PATH)
    sys_a = read_system_prompt(PROMPT_CALL_A_PATH)
    sys_b = read_system_prompt(PROMPT_CALL_B_PATH)
    user_a_template = read_user_template(PROMPT_CALL_A_PATH, "sample_id: {sample_id}")
    user_b_template = read_user_template(PROMPT_CALL_B_PATH, "sample_id: {sample_id}")
    print(f"[prompts] call_a_sha256={prompt_a_sha[:16]}... "
          f"call_b_sha256={prompt_b_sha[:16]}...")
    # --- Manifest resume ---
    manifest_path = run_dir / "manifest.jsonl"
    v2_path = run_dir / "layer_d_v2.jsonl"
    completed: set[str] = set()
    if manifest_path.exists():
        for row in load_jsonl(manifest_path):
            if row.get("status") == "ok":
                completed.add(row["sample_id"])
        print(f"[resume] skipping {len(completed)} already-completed sample_id(s) "
              f"from {manifest_path}")
    # --- Run (two-phase per sample) ---
    n_ok = 0
    n_failed = 0
    n_skipped_resume = 0
    n_calls_done = 0
    for i, sample in enumerate(subset, 1):
        if sample["sample_id"] in completed:
            n_skipped_resume += 1
            continue
        if n_calls_done + 2 > args.max_calls:
            print(f"[stop] max-calls={args.max_calls} would be exceeded; "
                  f"stopping at sample {i}/{n_samples}. Re-run with the same "
                  f"--run-id to resume.")
            break
        b_text = b_idx.get(sample["sample_id"], "")
        c_row = c_idx.get(sample["sample_id"]) or {}
        six_en_json = six_element_candidate_to_english_json(c_row)
        call_a_user = render_call_a(sample, b_text, six_en_json, user_a_template)
        # ---- Phase 1: Call A ----
        last_error: str | None = None
        resp_a: dict | None = None
        text_a: str = ""
        tokens_a: tuple[int, int] = (0, 0)
        elapsed_a: int = 0
        attempts_a: int = 0
        for attempt in range(1, args.max_attempts + 1):
            attempts_a = attempt
            t0 = time.time()
            try:
                resp_a = call_chat_completion(
                    base_url=args.base_url, api_key=api_key,
                    model=args.model, system_prompt=sys_a,
                    user_message=call_a_user,
                    max_tokens=args.max_tokens, temperature=args.temperature,
                    timeout_seconds=args.timeout_seconds,
                    thinking_mode=args.thinking_mode,
                )
                elapsed_a = int((time.time() - t0) * 1000)
                text_a = extract_assistant_text(resp_a)
                tokens_a = extract_token_usage(resp_a)
                break
            except Exception as e:
                last_error = repr(e)
                if attempt < args.max_attempts:
                    time.sleep(2 ** attempt)
        if resp_a is None:
            append_jsonl(manifest_path, {
                "sample_id": sample["sample_id"],
                "legacy_record_id": sample["legacy_record_id"],
                "status": "failed",
                "provider": args.provider,
                "model": args.model,
                "call": "A",
                "error_type": "call_a_failed",
                "error": f"Call A failed after {args.max_attempts} attempts: {last_error}",
                "retries": attempts_a,
                "run_id": run_id,
                "timestamp_utc": now_utc(),
            })
            n_failed += 1
            n_calls_done += 1
            continue
        try:
            obj_a = extract_first_json_object(text_a)
        except Exception as e:
            append_jsonl(manifest_path, {
                "sample_id": sample["sample_id"],
                "legacy_record_id": sample["legacy_record_id"],
                "status": "failed",
                "provider": args.provider,
                "model": args.model,
                "call": "A",
                "error_type": "call_a_unparseable",
                "error": f"Call A unparseable: {e!r}",
                "retries": attempts_a,
                "run_id": run_id,
                "timestamp_utc": now_utc(),
            })
            n_failed += 1
            n_calls_done += 1
            continue
        text_zh = obj_a.get("text_zh")
        clauses = obj_a.get("clauses") or []
        if not isinstance(text_zh, str) or not text_zh.strip():
            append_jsonl(manifest_path, {
                "sample_id": sample["sample_id"],
                "legacy_record_id": sample["legacy_record_id"],
                "status": "failed",
                "provider": args.provider,
                "model": args.model,
                "call": "A",
                "error_type": "empty_text_zh",
                "error": "Call A returned empty text_zh",
                "retries": attempts_a,
                "run_id": run_id,
                "timestamp_utc": now_utc(),
            })
            n_failed += 1
            n_calls_done += 1
            continue
        if not isinstance(clauses, list) or not clauses:
            append_jsonl(manifest_path, {
                "sample_id": sample["sample_id"],
                "legacy_record_id": sample["legacy_record_id"],
                "status": "failed",
                "provider": args.provider,
                "model": args.model,
                "call": "A",
                "error_type": "empty_clauses",
                "error": "Call A returned empty/non-list clauses",
                "retries": attempts_a,
                "run_id": run_id,
                "timestamp_utc": now_utc(),
            })
            n_failed += 1
            n_calls_done += 1
            continue
        n_calls_done += 1

        # ---- Phase 2: Call B (BLIND) ----
        if n_calls_done + 1 > args.max_calls:
            append_jsonl(manifest_path, {
                "sample_id": sample["sample_id"],
                "legacy_record_id": sample["legacy_record_id"],
                "status": "failed",
                "provider": args.provider,
                "model": args.model,
                "call": "B",
                "error_type": "max_calls_exceeded",
                "error": f"max-calls={args.max_calls} would be exceeded before Call B",
                "retries": 0,
                "run_id": run_id,
                "timestamp_utc": now_utc(),
            })
            n_failed += 1
            break
        call_b_user = render_call_b(sample, text_zh, user_b_template)
        try:
            assert_call_b_payload_is_clean(call_b_user, sample, b_text)
        except SystemExit as e:
            append_jsonl(manifest_path, {
                "sample_id": sample["sample_id"],
                "legacy_record_id": sample["legacy_record_id"],
                "status": "failed",
                "provider": args.provider,
                "model": args.model,
                "call": "B",
                "error_type": "call_b_payload_not_clean",
                "error": f"Call B payload failed clean-payload assertion: {e!r}",
                "retries": 0,
                "call_b_payload_clean": False,
                "run_id": run_id,
                "timestamp_utc": now_utc(),
            })
            n_failed += 1
            n_calls_done += 1
            continue
        resp_b: dict | None = None
        text_b: str = ""
        tokens_b: tuple[int, int] = (0, 0)
        elapsed_b: int = 0
        attempts_b: int = 0
        for attempt in range(1, args.max_attempts + 1):
            attempts_b = attempt
            t0 = time.time()
            try:
                resp_b = call_chat_completion(
                    base_url=args.base_url, api_key=api_key,
                    model=args.model, system_prompt=sys_b,
                    user_message=call_b_user,
                    max_tokens=args.max_tokens, temperature=args.temperature,
                    timeout_seconds=args.timeout_seconds,
                    thinking_mode=args.thinking_mode,
                )
                elapsed_b = int((time.time() - t0) * 1000)
                text_b = extract_assistant_text(resp_b)
                tokens_b = extract_token_usage(resp_b)
                break
            except Exception as e:
                last_error = repr(e)
                if attempt < args.max_attempts:
                    time.sleep(2 ** attempt)
        if resp_b is None:
            append_jsonl(manifest_path, {
                "sample_id": sample["sample_id"],
                "legacy_record_id": sample["legacy_record_id"],
                "status": "failed",
                "provider": args.provider,
                "model": args.model,
                "call": "B",
                "error_type": "call_b_failed",
                "error": f"Call B failed after {args.max_attempts} attempts: {last_error}",
                "retries": attempts_b,
                "run_id": run_id,
                "timestamp_utc": now_utc(),
            })
            n_failed += 1
            n_calls_done += 1
            continue
        try:
            obj_b = extract_first_json_object(text_b)
        except Exception as e:
            append_jsonl(manifest_path, {
                "sample_id": sample["sample_id"],
                "legacy_record_id": sample["legacy_record_id"],
                "status": "failed",
                "provider": args.provider,
                "model": args.model,
                "call": "B",
                "error_type": "call_b_unparseable",
                "error": f"Call B unparseable: {e!r}",
                "retries": attempts_b,
                "run_id": run_id,
                "timestamp_utc": now_utc(),
            })
            n_failed += 1
            n_calls_done += 1
            continue
        back_translation_en = obj_b.get("back_translation_en")
        if not isinstance(back_translation_en, str) or not back_translation_en.strip():
            append_jsonl(manifest_path, {
                "sample_id": sample["sample_id"],
                "legacy_record_id": sample["legacy_record_id"],
                "status": "failed",
                "provider": args.provider,
                "model": args.model,
                "call": "B",
                "error_type": "empty_back_translation",
                "error": "Call B returned empty back_translation_en",
                "retries": attempts_b,
                "run_id": run_id,
                "timestamp_utc": now_utc(),
            })
            n_failed += 1
            n_calls_done += 1
            continue
        n_calls_done += 1

        v2_row = {
            "sample_id": sample["sample_id"],
            "legacy_record_id": sample["legacy_record_id"],
            "text_zh": text_zh,
            "back_translation_en": back_translation_en,
            "clauses": clauses,
            "aid_source": "authorized_real_llm_call",
            "provider": args.provider,
            "model": args.model,
            "prompt_sha256": prompt_a_sha,
            "call_b_prompt_sha256": prompt_b_sha,
            "run_id": run_id,
            "immutable": True,
        }
        append_jsonl(v2_path, v2_row)
        append_jsonl(manifest_path, {
            "sample_id": sample["sample_id"],
            "legacy_record_id": sample["legacy_record_id"],
            "status": "ok",
            "provider": args.provider,
            "model": args.model,
            "call_a_prompt_sha256": prompt_a_sha,
            "call_b_prompt_sha256": prompt_b_sha,
            "call_a_prompt_tokens": tokens_a[0],
            "call_a_completion_tokens": tokens_a[1],
            "call_a_elapsed_ms": elapsed_a,
            "call_b_prompt_tokens": tokens_b[0],
            "call_b_completion_tokens": tokens_b[1],
            "call_b_elapsed_ms": elapsed_b,
            "call_a_retries": attempts_a,
            "call_b_retries": attempts_b,
            "call_b_payload_clean": True,
            "run_id": run_id,
            "timestamp_utc": now_utc(),
        })
        n_ok += 1
    # A recovered sample is appended after the rows that succeeded in an
    # earlier process. Restore deterministic source ordering before any
    # validator or promoter sees the candidate file.
    normalize_v2_order(v2_path)
    # --- Write run_summary.json (no API key) ---
    summary = {
        "run_id": run_id,
        "provider": args.provider,
        "model": args.model,
        "base_url": args.base_url,
        "n_samples_in_range": n_samples,
        "n_ok": n_ok,
        "n_failed": n_failed,
        "n_skipped_resume": n_skipped_resume,
        "calls_done": n_calls_done,
        "max_calls": args.max_calls,
        "timestamp_utc": now_utc(),
    }
    (run_dir / "run_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print()
    print(f"[done] n_ok={n_ok} n_failed={n_failed} n_skipped_resume={n_skipped_resume} "
          f"calls_done={n_calls_done}/{args.max_calls}")
    print(f"  run_id     : {run_id}")
    print(f"  run_dir    : {run_dir}")
    print(f"  manifest   : {manifest_path}")
    print(f"  v2 rows    : {v2_path}")
    print(f"  run_config : {run_dir / 'run_config.json'}")
    print(f"  run_summary: {run_dir / 'run_summary.json'}")
    print()
    print("Next step: validate with `scripts/validate_layer_d_v2.py "
          f"--run-dir {run_dir} [--allow-partial-pilot N]. "
          f"After a full 150-pass validation, run "
          f"`scripts/promote_layer_d_v2.py --run-dir {run_dir}` to "
          f"atomically activate the v2 Layer D file.")
    return 0 if n_failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
