# -*- coding: utf-8 -*-
"""Winter et al. (2020) Stage 3 development wrapper - package init."""

from bpc_hybrid.winter_stage3.winter_clause import parse_regulation_paragraph
from bpc_hybrid.winter_stage3.winter_model import parse_bpmn_file_winter
from bpc_hybrid.winter_stage3.winter_pair import WinterPair
from bpc_hybrid.winter_stage3.winter_similarity import WinterSimilarity

__all__ = [
    "parse_regulation_paragraph",
    "parse_bpmn_file_winter",
    "WinterPair",
    "WinterSimilarity",
]
