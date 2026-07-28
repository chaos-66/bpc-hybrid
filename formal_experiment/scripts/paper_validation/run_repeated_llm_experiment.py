"""Phase 2 executor: run a single (method, repeat) of the paper validation R1 experiment.

This is a wrapper that:
- reads the frozen batch file
- reads the Gold and B0 inputs
- builds the appropriate Prompt (D1 / H1-primed / H1-empty)
- calls the LLM (real API in normal mode; --dry-run skips calls)
- writes the per-batch output structure required by the task
- supports --resume (no overwrite of completed batches)
- supports --smoke (only batch 1, first 3 records)
- sanitizes request metadata (no API key, no Authorization)
- retries at most 3 times per batch for transient errors only

CLI flags:
  --experiment-id    e.g. paper_validation_r1_20260728
  --method           d1_unprimed | h1_selective_primed | h1_selective_empty
  --repeat-id        1 | 2 | 3
  --batch-file       path to frozen_batches.json
  --output-root      e.g. formal_experiment/outputs/paper_validation_r1_20260728
  --dry-run          build the request but do not call the API
  --smoke            use only the first 3 record_ids of batch 1
  --resume           skip completed batches (default True)
  --gold-path        override gold path (default uses project standard)
  --b0-path          override b0 path
  --prompts-dir      override prompts dir
  --env-path         override .env path
"""
import argparse
import hashlib
import json
import os
import re
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


# ---------------------------------------------------------------------------
# .env loader (key names only, never printed)
# ---------------------------------------------------------------------------

def load_env_silently(env_path: Path) -> None:
    if not env_path.exists():
        return
    with open(env_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            k, v = line.split('=', 1)
            k = k.strip()
            v = v.strip().strip('"').strip("'")
            if k and k not in os.environ:
                os.environ[k] = v


# ---------------------------------------------------------------------------
# Gold + B0 + record_id loading
# ---------------------------------------------------------------------------

def load_gold(gold_path: Path) -> dict[str, dict[str, Any]]:
    """Returns {sample_id: {approved_text_en, gold_clauses:[{clause_text, modality, clause_id}]}}."""
    with open(gold_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    out: dict[str, dict[str, Any]] = {}
    for r in data.get('records', []):
        hc = r.get('human_correction', {}) or {}
        text = hc.get('approved_text_en') or r.get('approved_text_en') or ''
        clauses = []
        for c in (hc.get('clauses') or []):
            mod = c.get('modality', {}) or {}
            if not isinstance(mod, dict):
                continue
            if mod.get('decision') not in ('accepted', 'edited'):
                continue
            mv = mod.get('value')
            if mv not in ('permission', 'obligation', 'prohibition', 'definition'):
                continue
            cspan = c.get('clause_span', {}) or {}
            clauses.append({
                'clause_id': c.get('clause_id'),
                'clause_text': cspan.get('text', ''),
                'modality': mv,
            })
        out[r['sample_id']] = {
            'sample_id': r['sample_id'],
            'approved_text_en': text,
            'gold_clauses': clauses,
        }
    return out


def load_b0(b0_path: Path) -> dict[str, list[dict[str, Any]]]:
    with open(b0_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    out: dict[str, list[dict[str, Any]]] = {}
    for r in data:
        sid = r.get('sample_id')
        rec = r.get('record', {}) or {}
        clauses = []
        for c in (rec.get('clauses') or []):
            mod = (c.get('modality') or {}).get('label')
            if mod not in ('permission', 'obligation', 'prohibition', 'definition'):
                continue
            cspan = c.get('clause_span', {}) or {}
            text = cspan.get('text', '')
            if not text:
                continue
            clauses.append({
                'clause_id': c.get('clause_id'),
                'clause_text': text,
                'modality': mod,
            })
        out[sid] = clauses
    return out


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------

def load_prompt(prompts_dir: Path, name: str) -> tuple[str, str]:
    """Read a normalized prompt file. Returns (system, user_template)."""
    p = prompts_dir / name
    with open(p, 'r', encoding='utf-8') as f:
        text = f.read()
    # Split on the markers
    m = re.search(r'=== SYSTEM ===\n(.*?)\n\n=== USER TEMPLATE ===\n(.*)\n?$', text, re.DOTALL)
    if not m:
        raise ValueError(f'cannot parse prompt file {p}')
    return m.group(1), m.group(2)


def build_d1_user(user_template: str, source_text: str) -> str:
    # The D1 user template uses {source_text}
    return user_template.replace('{source_text}', source_text)


def build_h1_user(user_template: str, source_text: str, b0_clauses: list[dict[str, Any]] | None) -> str:
    """For H1 (primed and empty):
    - {source_text} is the source text
    - The b0 placeholder is either {b0_predictions} (primed file) or
      {b0_predictions_block} (empty file). Both are runtime placeholders.
    """
    if b0_clauses is None or len(b0_clauses) == 0:
        b0_block = '(B0 made no predictions for this source)'
    else:
        b0_block = '\n'.join(
            f'- "{c["clause_text"][:200]}" -> {c["modality"]}'
            for c in b0_clauses
        )
    out = user_template
    out = out.replace('{source_text}', source_text)
    # Replace whichever placeholder is present.
    out = out.replace('{b0_predictions_block}', b0_block)
    out = out.replace('{b0_predictions}', b0_block)
    return out


# ---------------------------------------------------------------------------
# JSON parsing (deterministic fixes only)
# ---------------------------------------------------------------------------

def parse_llm_json(text: str) -> tuple[dict | list | None, list[str]]:
    """Parse an LLM JSON response with deterministic cleanup only.

    Allowed repairs (no LLM, no Gold-based repair, no guessing):
    - strip leading/trailing whitespace
    - strip UTF-8 BOM
    - strip Markdown code fences (```json ... ``` or ``` ... ```)
    - strip leading/trailing non-JSON text (find first '{' or '[' and last matching '}' or ']')
    Returns (parsed, list_of_repairs_made).
    """
    repairs: list[str] = []
    if text is None:
        return None, repairs
    s = text
    # BOM
    if s.startswith('\ufeff'):
        s = s.lstrip('\ufeff')
        repairs.append('stripped_utf8_bom')
    s = s.strip()
    # Markdown fences
    fence_match = re.search(r'```(?:json)?\s*(.*?)\s*```', s, re.DOTALL)
    if fence_match:
        s = fence_match.group(1)
        repairs.append('stripped_markdown_fence')
    s = s.strip()
    # If still not starting with JSON, find first '{' or '['
    if not s:
        return None, repairs + ['empty_after_strip']
    if s[0] not in '{[':
        idx = max(s.find('{'), s.find('['))
        if idx > 0:
            s = s[idx:]
            repairs.append('stripped_leading_nonjson')
    # Trim trailing non-JSON
    if s[-1] not in '}]':
        idx = max(s.rfind('}'), s.rfind(']'))
        if idx > 0:
            s = s[:idx + 1]
            repairs.append('stripped_trailing_nonjson')
    try:
        return json.loads(s), repairs
    except Exception:
        return None, repairs + ['json_loads_failed']


# ---------------------------------------------------------------------------
# Prediction extraction (per method)
# ---------------------------------------------------------------------------

MODALITY_SET = ('permission', 'obligation', 'prohibition', 'definition')


def extract_d1_predicted(parsed) -> list[dict[str, Any]]:
    """M1: extract {clause_text, modality} from the LLM's {"clauses": [...]}."""
    if not isinstance(parsed, dict):
        return []
    raw = parsed.get('clauses') or []
    if not isinstance(raw, list):
        return []
    out = []
    for c in raw:
        if not isinstance(c, dict):
            continue
        mod = c.get('modality')
        if mod not in MODALITY_SET:
            continue
        ct = c.get('clause_text') or ''
        if not isinstance(ct, str) or not ct.strip():
            continue
        out.append({'clause_text': ct, 'modality': mod})
    return out


def extract_h1_predicted(parsed) -> list[dict[str, Any]]:
    """M2/M3: build H1 = keep.clause_text + correct.corrected_text + add.clause_text.

    Each output item carries (clause_text, modality, decision, original_text).
    """
    if not isinstance(parsed, dict):
        return []
    out = []
    for k in (parsed.get('keep') or []):
        if not isinstance(k, dict):
            continue
        mod = k.get('modality')
        if mod not in MODALITY_SET:
            continue
        ct = k.get('clause_text') or ''
        if not ct:
            continue
        out.append({'clause_text': ct, 'modality': mod, 'decision': 'keep'})
    for c in (parsed.get('correct') or []):
        if not isinstance(c, dict):
            continue
        mod = c.get('corrected_modality')
        if mod not in MODALITY_SET:
            continue
        ct = c.get('corrected_text') or ''
        if not ct:
            continue
        out.append({
            'clause_text': ct,
            'modality': mod,
            'decision': 'corrected',
            'original_text': c.get('original_text', ''),
        })
    for a in (parsed.get('add') or []):
        if not isinstance(a, dict):
            continue
        mod = a.get('modality')
        if mod not in MODALITY_SET:
            continue
        ct = a.get('clause_text') or ''
        if not ct:
            continue
        out.append({'clause_text': ct, 'modality': mod, 'decision': 'added'})
    return out


# ---------------------------------------------------------------------------
# API call (POST /chat/completions)
# ---------------------------------------------------------------------------

def call_llm(
    system: str,
    user: str,
    base_url: str,
    api_key: str,
    model: str,
    temperature: float,
    response_format: str,
    max_tokens: int,
    timeout: int,
) -> tuple[dict, dict, dict]:
    """Returns (response_dict, usage_dict, request_metadata_dict)."""
    import requests  # local import to keep module-level import light
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json',
    }
    payload = {
        'model': model,
        'messages': [
            {'role': 'system', 'content': system},
            {'role': 'user', 'content': user},
        ],
        'response_format': {'type': response_format},
        'temperature': temperature,
        'max_tokens': max_tokens,
    }
    t0 = time.time()
    resp = requests.post(
        f'{base_url.rstrip("/")}/chat/completions',
        headers=headers,
        json=payload,
        timeout=timeout,
    )
    t1 = time.time()
    resp.raise_for_status()
    data = resp.json()
    usage = data.get('usage', {}) or {}
    meta = {
        'latency_s': round(t1 - t0, 3),
        'status_code': resp.status_code,
    }
    return data, usage, meta


# ---------------------------------------------------------------------------
# Atomic write helpers
# ---------------------------------------------------------------------------

def atomic_write_json(path: Path, obj: Any) -> None:
    """Write JSON to a temp file, then atomic-rename. Refuses to overwrite."""
    tmp = path.with_suffix(path.suffix + '.tmp')
    if path.exists():
        # Caller should have checked already; raise rather than silently overwrite.
        raise FileExistsError(f'refusing to overwrite {path}')
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def atomic_write_text(path: Path, text: str) -> None:
    tmp = path.with_suffix(path.suffix + '.tmp')
    if path.exists():
        raise FileExistsError(f'refusing to overwrite {path}')
    with open(tmp, 'w', encoding='utf-8') as f:
        f.write(text)
    os.replace(tmp, path)


def append_jsonl(path: Path, obj: dict) -> None:
    """Append a single JSON line. Used for parse_errors / api_errors."""
    line = json.dumps(obj, ensure_ascii=False) + '\n'
    with open(path, 'a', encoding='utf-8') as f:
        f.write(line)


def file_sha256(path: Path) -> str:
    with open(path, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()


# ---------------------------------------------------------------------------
# Sanitized request metadata
# ---------------------------------------------------------------------------

def build_request_metadata(
    method: str,
    repeat_id: int,
    batch_id: int,
    record_ids: list[str],
    model: str,
    api_host: str,
    temperature: float,
    response_format: str,
    prompt_sha256: str,
    input_sha256: str,
    request_started_at: str,
    request_finished_at: str,
    attempt_count: int,
    status: str,
) -> dict:
    return {
        'method': method,
        'repeat_id': repeat_id,
        'batch_id': batch_id,
        'record_ids': list(record_ids),
        'model': model,
        'api_host': api_host,
        'temperature': temperature,
        'response_format': response_format,
        'prompt_sha256': prompt_sha256,
        'input_sha256': input_sha256,
        'request_started_at': request_started_at,
        'request_finished_at': request_finished_at,
        'attempt_count': attempt_count,
        'status': status,
    }


# ---------------------------------------------------------------------------
# Main executor
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser()
    ap.add_argument('--experiment-id', required=True)
    ap.add_argument('--method', required=True,
                    choices=['d1_unprimed', 'h1_selective_primed', 'h1_selective_empty'])
    ap.add_argument('--repeat-id', required=True, type=int)
    ap.add_argument('--batch-file', required=True)
    ap.add_argument('--output-root', required=True)
    ap.add_argument('--gold-path', default='formal_experiment/data/development/human_review/estg_150_human_correction_v1.json')
    ap.add_argument('--b0-path', default='formal_experiment/outputs/development/s27_estg150_b0_enhanced_v10a/b0_attempts.json')
    ap.add_argument('--prompts-dir', default='formal_experiment/outputs/paper_validation_r1_20260728/prompts')
    ap.add_argument('--env-path', default='formal_experiment/.env')
    ap.add_argument('--model', default='deepseek-v4-pro')
    ap.add_argument('--temperature', type=float, default=0)
    ap.add_argument('--response-format', default='json_object')
    ap.add_argument('--max-tokens', type=int, default=4000)
    ap.add_argument('--timeout', type=int, default=180)
    ap.add_argument('--max-retry', type=int, default=3)
    ap.add_argument('--dry-run', action='store_true', help='build request, do not call API')
    ap.add_argument('--smoke', action='store_true', help='use only first 3 record_ids of batch 1')
    ap.add_argument('--resume', action='store_true', default=True)
    ap.add_argument('--no-resume', dest='resume', action='store_false')
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    exp_id = args.experiment_id
    method = args.method
    repeat_id = args.repeat_id
    out_root = Path(args.output_root)
    repeat_dir = out_root / 'runs' / method / f'repeat_{repeat_id:02d}'
    if repeat_dir.exists():
        # Resume only if --resume; otherwise the caller is at fault.
        if not args.resume:
            print(f'ERROR: {repeat_dir} already exists; use --resume to continue')
            return 2
        print(f'Resume mode: continuing under {repeat_dir}')

    # Load frozen batches
    with open(args.batch_file, 'r', encoding='utf-8') as f:
        frozen = json.load(f)
    batches = frozen['batches']

    # Smoke narrows to batch 1 with first 3 ids
    if args.smoke:
        batches = [batches[0].copy()]
        batches[0]['record_ids'] = batches[0]['record_ids'][:3]

    # Load Gold and B0
    gold = load_gold(Path(args.gold_path))
    b0 = load_b0(Path(args.b0_path))

    # Load prompts
    prompts_dir = Path(args.prompts_dir)
    if method == 'd1_unprimed':
        system, user_template = load_prompt(prompts_dir, 'd1_prompt.txt')
    elif method == 'h1_selective_primed':
        system, user_template = load_prompt(prompts_dir, 'h1_selective_primed_prompt_template.txt')
    else:  # h1_selective_empty
        system, user_template = load_prompt(prompts_dir, 'h1_selective_empty_prompt_template.txt')
    prompt_sha = file_sha256(prompts_dir / (
        'd1_prompt.txt' if method == 'd1_unprimed' else
        'h1_selective_primed_prompt_template.txt' if method == 'h1_selective_primed' else
        'h1_selective_empty_prompt_template.txt'
    ))

    # Load .env (keys only into env, never into outputs)
    load_env_silently(Path(args.env_path))
    base_url = os.environ.get('BPC_HYBRID_LLM_BASE_URL', '')
    api_key = os.environ.get('BPC_HYBRID_LLM_API_KEY', '')
    if not base_url and not args.dry_run:
        print('ERROR: BPC_HYBRID_LLM_BASE_URL is empty; aborting')
        return 2
    if not api_key and not args.dry_run:
        print('ERROR: BPC_HYBRID_LLM_API_KEY is empty; aborting')
        return 2
    api_host = urlparse(base_url).netloc if base_url else '(dry-run)'

    # Create per-repeat top-level manifest
    repeat_dir.mkdir(parents=True, exist_ok=True)
    run_manifest = {
        'experiment_id': exp_id,
        'method': method,
        'repeat_id': repeat_id,
        'created_at_utc': datetime.now(timezone.utc).isoformat(),
        'model': args.model,
        'temperature': args.temperature,
        'response_format': args.response_format,
        'max_tokens': args.max_tokens,
        'max_retry': args.max_retry,
        'api_host': api_host,
        'prompt_sha256': prompt_sha,
        'batches': [{'batch_id': b['batch_id'], 'record_count': len(b['record_ids'])} for b in batches],
        'dry_run': args.dry_run,
        'smoke': args.smoke,
    }
    atomic_write_json(repeat_dir / 'run_manifest.json', run_manifest)

    # Per-batch processing
    cumulative = {
        'in_tok': 0,
        'out_tok': 0,
        'attempts': 0,
        'retries_for_transient': 0,
        'parse_failures': 0,
    }
    for b in batches:
        bid = b['batch_id']
        rids = b['record_ids']
        batch_dir = repeat_dir / f'batch_{bid:02d}'
        batch_dir.mkdir(parents=True, exist_ok=True)
        # Resume: skip if a successful response is already on disk.
        if args.resume and (batch_dir / 'request_metadata.json').exists():
            try:
                with open(batch_dir / 'request_metadata.json', 'r', encoding='utf-8') as f:
                    prev = json.load(f)
                if prev.get('status') == 'success' and (batch_dir / 'parsed_predictions.json').exists():
                    print(f'[skip] batch {bid} already succeeded')
                    # Still add to cumulative if not present
                    for k, src in [('input_tokens', 'usage.json')]:
                        pass
                    continue
            except Exception:
                pass

        # Build request text per record
        per_record_prompts: list[dict[str, str]] = []
        for rid in rids:
            if rid not in gold:
                append_jsonl(batch_dir / 'api_errors.jsonl', {
                    'record_id': rid, 'error': 'missing_in_gold',
                })
                continue
            source_text = gold[rid]['approved_text_en']
            if method == 'd1_unprimed':
                user_text = build_d1_user(user_template, source_text)
            else:
                b0_clauses = b0.get(rid, [])
                user_text = build_h1_user(user_template, source_text, b0_clauses)
            per_record_prompts.append({'record_id': rid, 'source_text': source_text, 'user_text': user_text})

        # We send ONE request that batches all 30 record prompts concatenated.
        # This matches the existing paper pilot scripts (which also concatenate
        # 30 records into one LLM call per batch).
        # Concatenation rule: each record's prompt is appended verbatim, separated
        # by a sentinel "\n\n===== RECORD <rid> =====\n\n".
        # We then parse each section independently. This keeps the schema
        # independent per record.
        if method == 'd1_unprimed':
            sections = []
            for pr in per_record_prompts:
                sections.append(
                    f'===== RECORD {pr["record_id"]} =====\n' +
                    pr['user_text']
                )
            combined_user = '\n\n'.join(sections) + '\n\nIMPORTANT: Return a JSON object with one top-level key "results" mapping each record_id to {"clauses": [...]}.\n'
            response_schema = 'd1'
        else:
            sections = []
            for pr in per_record_prompts:
                sections.append(
                    f'===== RECORD {pr["record_id"]} =====\n' +
                    pr['user_text']
                )
            combined_user = '\n\n'.join(sections) + '\n\nIMPORTANT: Return a JSON object with one top-level key "results" mapping each record_id to {"keep": [...], "correct": [...], "remove": [...], "add": [...]} per the schema above.\n'
            response_schema = 'h1'

        # Compute input SHA over the EXACT bytes we'd send
        body_for_hash = (system + '\n' + combined_user).encode('utf-8')
        input_sha = hashlib.sha256(body_for_hash).hexdigest()

        # Call API (with retry for transient errors)
        attempts = 0
        last_error: dict | None = None
        response = None
        usage = {}
        meta = {}
        parse_repairs: list[str] = []
        parsed_obj = None
        started_at = datetime.now(timezone.utc).isoformat()
        for attempt in range(1, args.max_retry + 1):
            attempts = attempt
            if args.dry_run:
                # In dry-run, do not call API; record what we would have done.
                response = None
                usage = {'prompt_tokens': 0, 'completion_tokens': 0, 'total_tokens': 0}
                meta = {'status_code': 0, 'latency_s': 0, 'dry_run': True}
                break
            try:
                response, usage, meta = call_llm(
                    system=system,
                    user=combined_user,
                    base_url=base_url,
                    api_key=api_key,
                    model=args.model,
                    temperature=args.temperature,
                    response_format=args.response_format,
                    max_tokens=args.max_tokens,
                    timeout=args.timeout,
                )
                # Try parse
                content = response['choices'][0]['message']['content']
                parsed_obj, parse_repairs = parse_llm_json(content)
                if parsed_obj is None:
                    raise ValueError('parse_failed')
                break
            except Exception as e:
                tb = traceback.format_exc()
                last_error = {
                    'attempt': attempt,
                    'error': f'{type(e).__name__}: {e}'[:500],
                    'traceback': tb[-2000:],
                }
                # Log error
                append_jsonl(batch_dir / 'api_errors.jsonl', last_error)
                # Backoff
                time.sleep(min(2 ** attempt, 10))
        finished_at = datetime.now(timezone.utc).isoformat()

        if parsed_obj is None and not args.dry_run:
            # All retries failed
            meta_status = 'failed'
            meta_attempts = attempts
        else:
            meta_status = 'success' if not args.dry_run else 'dry_run'
            meta_attempts = attempts

        # Save raw response (truncated) and parsed predictions
        if response is not None:
            raw = json.dumps(response, ensure_ascii=False)
        elif args.dry_run:
            raw = '(dry-run: no API call made)\n'
        else:
            raw = '(no response)\n'
        atomic_write_text(batch_dir / 'raw_response.txt', raw)

        # Predictions: per record
        per_record_predictions: dict[str, list[dict[str, Any]]] = {}
        parse_errors: list[dict] = []
        if parsed_obj is not None:
            if method == 'd1_unprimed':
                # Expect {'results': {rid: {'clauses': [...]}, ...}}
                # or {'clauses': [...]} for single-record responses
                results = parsed_obj.get('results') if isinstance(parsed_obj, dict) else None
                if isinstance(results, dict):
                    for rid, body in results.items():
                        if not isinstance(body, dict):
                            parse_errors.append({'record_id': rid, 'error': 'not_dict'})
                            continue
                        per_record_predictions[rid] = extract_d1_predicted(body)
                else:
                    # Fallback: treat parsed_obj as the single-batch response
                    # If we have only 1 record (smoke), assign to first rid.
                    if len(per_record_prompts) == 1:
                        rid = per_record_prompts[0]['record_id']
                        per_record_predictions[rid] = extract_d1_predicted(parsed_obj)
                    else:
                        parse_errors.append({'error': 'no_results_key_multi_record', 'parsed_keys': list(parsed_obj.keys()) if isinstance(parsed_obj, dict) else None})
            else:
                results = parsed_obj.get('results') if isinstance(parsed_obj, dict) else None
                if isinstance(results, dict):
                    for rid, body in results.items():
                        if not isinstance(body, dict):
                            parse_errors.append({'record_id': rid, 'error': 'not_dict'})
                            continue
                        per_record_predictions[rid] = extract_h1_predicted(body)
                else:
                    if len(per_record_prompts) == 1:
                        rid = per_record_prompts[0]['record_id']
                        per_record_predictions[rid] = extract_h1_predicted(parsed_obj)
                    else:
                        parse_errors.append({'error': 'no_results_key_multi_record', 'parsed_keys': list(parsed_obj.keys()) if isinstance(parsed_obj, dict) else None})
        else:
            parse_errors.append({'error': 'all_attempts_failed', 'last': last_error})

        # Persist parsed_predictions.json
        atomic_write_json(batch_dir / 'parsed_predictions.json', {
            'method': method,
            'repeat_id': repeat_id,
            'batch_id': bid,
            'record_ids': rids,
            'response_schema_expected': response_schema,
            'parse_repairs': parse_repairs,
            'per_record': per_record_predictions,
            'all_clauses': [
                {'record_id': rid, **clause}
                for rid, lst in per_record_predictions.items()
                for clause in lst
            ],
        })
        # Persist parse_errors.jsonl
        for pe in parse_errors:
            append_jsonl(batch_dir / 'parse_errors.jsonl', pe)
        # Persist request_metadata.json
        req_meta = build_request_metadata(
            method=method,
            repeat_id=repeat_id,
            batch_id=bid,
            record_ids=rids,
            model=args.model,
            api_host=api_host,
            temperature=args.temperature,
            response_format=args.response_format,
            prompt_sha256=prompt_sha,
            input_sha256=input_sha,
            request_started_at=started_at,
            request_finished_at=finished_at,
            attempt_count=meta_attempts,
            status=meta_status,
        )
        req_meta['prompt_tokens'] = usage.get('prompt_tokens', 0) if isinstance(usage, dict) else 0
        req_meta['completion_tokens'] = usage.get('completion_tokens', 0) if isinstance(usage, dict) else 0
        req_meta['total_tokens'] = usage.get('total_tokens', 0) if isinstance(usage, dict) else 0
        req_meta['latency_s'] = meta.get('latency_s', 0)
        req_meta['parse_repairs'] = parse_repairs
        atomic_write_json(batch_dir / 'request_metadata.json', req_meta)

        # Update cumulative
        if isinstance(usage, dict):
            cumulative['in_tok'] += int(usage.get('prompt_tokens', 0) or 0)
            cumulative['out_tok'] += int(usage.get('completion_tokens', 0) or 0)
        cumulative['attempts'] += meta_attempts

    # Write per-repeat top-level summaries
    atomic_write_json(repeat_dir / 'token_usage.json', {
        'experiment_id': exp_id,
        'method': method,
        'repeat_id': repeat_id,
        'input_tokens': cumulative['in_tok'],
        'output_tokens': cumulative['out_tok'],
        'total_tokens': cumulative['in_tok'] + cumulative['out_tok'],
        'attempts': cumulative['attempts'],
        'parse_failures': cumulative['parse_failures'],
    })
    # timing.json: per-batch latency
    timing = []
    for b in batches:
        bid = b['batch_id']
        bp = repeat_dir / f'batch_{bid:02d}' / 'request_metadata.json'
        if bp.exists():
            try:
                with open(bp, 'r', encoding='utf-8') as f:
                    t = json.load(f)
                timing.append({'batch_id': bid, 'latency_s': t.get('latency_s', 0), 'status': t.get('status')})
            except Exception:
                pass
    atomic_write_json(repeat_dir / 'timing.json', {'method': method, 'repeat_id': repeat_id, 'per_batch': timing})

    print(f'WROTE {repeat_dir}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
