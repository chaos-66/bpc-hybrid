"""Pytest discovery for the paper_validation tests."""
import sys
from pathlib import Path

# Make the scripts directory importable for unit-tested functions
ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / 'scripts' / 'paper_validation'
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
