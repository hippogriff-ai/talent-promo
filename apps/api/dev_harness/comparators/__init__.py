"""Comparison logic for evaluating prompt outputs.

Two types of comparators:
1. StructuredComparator - Programmatic comparison for structured data
2. LLMJudgeComparator - LLM-as-judge for unstructured/subjective evaluation
"""

from .structured import StructuredComparator
from .llm_judge import LLMJudgeComparator

__all__ = ["StructuredComparator", "LLMJudgeComparator"]
