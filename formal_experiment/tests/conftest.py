"""Narrow test-harness protections for mutable tamper fixtures.

The Stage 1 tamper tests intentionally rewrite frozen JSON artifacts and
restore their original bytes in ``finally`` blocks.  On Windows, an
intermittent ``OSError(EINVAL)`` can occur while reopening the just-verified
file for restoration.  A failed restore contaminates every later integrity
test, so these specific test modules retry the same byte-exact write briefly.
The payload is unchanged, the retry is bounded, and non-transient errors still
fail the test.
"""

from __future__ import annotations

import errno
import time
from pathlib import Path

import pytest


_STAGE1_MUTATING_MODULES = {
    "test_stage1_adjudication_batch2.py",
    "test_stage1_adjudication_batch3.py",
    "test_stage1_adjudication_batch4.py",
    "test_stage1_adjudication_batch5.py",
    "test_stage1_adjudication_batch6.py",
    "test_stage1_adjudication_batch7.py",
    "test_stage1_adjudication_chain.py",
    "test_stage1_human_adjudication.py",
    "test_stage1_process_gold.py",
}
_RETRYABLE_WINDOWS_ERRNOS = {errno.EINVAL, errno.EACCES, errno.EBUSY}


@pytest.fixture(autouse=True)
def _retry_stage1_tamper_restore_writes(request, monkeypatch):
    """Retry only byte writes made by the Stage 1 tamper-test modules."""
    if request.node.path.name not in _STAGE1_MUTATING_MODULES:
        yield
        return

    original_write_bytes = Path.write_bytes

    def write_bytes_with_bounded_retry(path: Path, data: bytes) -> int:
        for attempt in range(20):
            try:
                return original_write_bytes(path, data)
            except OSError as exc:
                if exc.errno not in _RETRYABLE_WINDOWS_ERRNOS or attempt == 19:
                    raise
                time.sleep(0.05 * (attempt + 1))
        raise AssertionError("unreachable")

    monkeypatch.setattr(Path, "write_bytes", write_bytes_with_bounded_retry)
    yield
