# -*- coding: utf-8 -*-
"""Offline precheck of the real-run process environment (ZERO API / ZERO .env).

Both real executors build their config with
``LLMConfig.from_env(project_root=ROOT, load_project_env=False)`` — only the
process environment is read; the project ``.env`` is never opened.  This tool
reports exactly what the executors will resolve and whether their per-run
hard conditions hold:

* flat keys ``BPC_HYBRID_LLM_ENABLED/PROVIDER/MODEL/BASE_URL/API_KEY/
  MAX_TOKENS/TEMPERATURE/TOP_P`` (or, when ``BPC_HYBRID_LLM_PROFILE=deepseek``
  is set, the ``BPC_HYBRID_DeepSeek_*`` equivalents);
* S2.12 arms require provider != mock, enabled=true, model ==
  ``deepseek-v4-pro`` (payload/model/sampling are additionally payload-locked
  per call by the executors);
* the GDPR arm additionally requires an API key and
  base_url == ``https://api.deepseek.com/v1``.

Secrets are never printed: the API key is reported only as a presence
boolean.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for candidate in (SRC,):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from bpc_hybrid.llm_config import LLMConfig  # noqa: E402

REQUIRED_MODEL = "deepseek-v4-pro"
LOCKED_BASE_URL = "https://api.deepseek.com/v1"


def main() -> int:
    try:
        config = LLMConfig.from_env(project_root=ROOT, load_project_env=False)
    except Exception as exc:  # LLMConfigError etc.; message never holds secrets
        print(f"LLMConfig.from_env refused: {exc}")
        print("API ENV NOT READY (offline precheck; no API call was made, "
              "no .env was read)")
        return 2
    print("LLMConfig.from_env(load_project_env=False) resolution")
    print(f"  enabled             : {config.enabled}")
    print(f"  provider            : {config.provider}")
    print(f"  model               : {config.model}")
    print(f"  base_url            : {config.base_url}")
    print(f"  api_key_present     : {bool(config.api_key)}")
    print(f"  max_tokens          : {config.max_tokens}")
    print(f"  temperature         : {config.temperature}")
    print(f"  top_p               : {config.top_p}")
    print(f"  seed                : {config.seed}")
    print(f"  seed_supported      : {config.seed_supported}")
    print(f"  timeout_seconds     : {config.timeout_seconds}")

    ok = True
    if config.provider == "mock" or not config.enabled:
        print("FAIL provider is mock or not enabled (process env only)")
        ok = False
    if config.model != REQUIRED_MODEL:
        print(f"FAIL model {config.model!r} != {REQUIRED_MODEL!r}")
        ok = False
    if config.base_url != LOCKED_BASE_URL:
        print(f"FAIL base_url {config.base_url!r} != {LOCKED_BASE_URL!r} "
              f"(required by the GDPR executor and the locked payloads)")
        ok = False
    if not config.api_key:
        print("FAIL API key absent (BPC_HYBRID_LLM_API_KEY or "
              "BPC_HYBRID_DeepSeek_API_KEY in the process environment)")
        ok = False
    if int(config.max_tokens or 0) != 4096:
        print(f"FAIL max_tokens {config.max_tokens!r} != 4096 (locked recipe)")
        ok = False
    if config.temperature != 0.0:
        print(f"FAIL temperature {config.temperature!r} != 0.0")
        ok = False
    if config.top_p != 1.0:
        print(f"FAIL top_p {config.top_p!r} != 1.0")
        ok = False

    print("API ENV READY" if ok else "API ENV NOT READY (offline precheck; "
          "no API call was made, no .env was read)")
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
