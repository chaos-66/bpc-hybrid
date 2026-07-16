"""Central paths for the formal experiment capsule."""

from pathlib import Path


PACKAGE_DIR = Path(__file__).resolve().parent
FORMAL_ROOT = PACKAGE_DIR.parents[1]
WORKSPACE_ROOT = FORMAL_ROOT.parent
REPO_ROOT = FORMAL_ROOT

CONFIG_DIR = FORMAL_ROOT / "configs"
PATHS_CONFIG = CONFIG_DIR / "paths.json"
METHODS_CONFIG = CONFIG_DIR / "methods.json"
EXPERIMENT_CONTRACT = CONFIG_DIR / "experiment_contract.json"
HUMAN_REVIEW_SCHEMA = CONFIG_DIR / "schemas" / "human_gold_review.schema.json"

ESTG_RECONSTRUCTION_SOURCE = (
    FORMAL_ROOT / "data/development/estg/estg_selected_150_en_llm_translated.jsonl"
)
HUMAN_REVIEW_PACK = (
    FORMAL_ROOT / "data/development/human_review/estg150_review_pack_v1.jsonl"
)

# The single human-editing surface for the EStG-150 v1 benchmark.
# v1 workflow: estg_150_canonical_review_v1.json (retired 2026-07-12 as
# workflow draft, preserved as provenance; not the active editing
# surface any more).
# v2 workflow: estg_150_human_correction_v1.json (LLM-assisted,
# human-adjudicated). This is the ONLY file the user edits.
# See docs/HUMAN_GOLD_GUIDE.md and
# data/development/human_review/ESTG150_REVIEW_WORKFLOW_V1.md.
CANONICAL_REVIEW_FILE = (
    FORMAL_ROOT / "data/development/human_review" /
    "estg_150_canonical_review_v1.json"
)
CANONICAL_REVIEW_SCHEMA = (
    FORMAL_ROOT / "configs/schemas" /
    "estg_150_canonical_review.schema.json"
)
HUMAN_CORRECTION_FILE = (
    FORMAL_ROOT / "data/development/human_review" /
    "estg_150_human_correction_v1.json"
)
ESTG_150_MEMBERSHIP_HASHES = (
    FORMAL_ROOT / "data/development/estg" / "estg_150_membership_hashes.json"
)

# Compatibility aliases for older helper scripts. They now point at the
# canonical EStG review route, not the retired GDPR-50 development route.
CURRENT_CANDIDATES = HUMAN_REVIEW_PACK
GOLD_REVIEW_TEMPLATE = HUMAN_REVIEW_PACK

WINTER_2020_REFERENCE_DIR = WORKSPACE_ROOT / "references/winter_2020_model_check"
SUN_ORIGINAL_REFERENCE_DIR = WORKSPACE_ROOT / "references/sun_2024_original"
SUN_PROGRAM_DIR = SUN_ORIGINAL_REFERENCE_DIR

SRC_DIR = FORMAL_ROOT / "src"
DEVELOPMENT_DIR = FORMAL_ROOT / "data/development"
FROZEN_INPUT_DIR = FORMAL_ROOT / "data/input"
FROZEN_GOLD_DIR = FORMAL_ROOT / "data/gold"
FORMAL_PREDICTIONS_DIR = FORMAL_ROOT / "data/predictions"
FORMAL_RESULTS_DIR = FORMAL_ROOT / "data/results"
FORMAL_REPORTS_DIR = FORMAL_ROOT / "outputs/reports"
