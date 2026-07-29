"""S2.6 canonical B0 entry point (no LLM).

The currently unlocked command runs the locked bilingual synthetic composition:
German text is sent only to the verified S2.4 classifier, while the aligned
English text and attested S2.5 CoreNLP/Tregex/Tsurgeon observations supply the
canonical evidence spans.  It does not read Gold or a real-data test set.

Batch prediction remains fail-closed until S2.2 freezes the shared input/Gold
and S2.10 locks the evaluator and output location.
"""

from __future__ import annotations

from verify_sun_b0_s26 import main


if __name__ == "__main__":
    raise SystemExit(main())
