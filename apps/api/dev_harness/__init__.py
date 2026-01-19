"""Dev harness for LLM prompt tuning with feedback loops.

Structure:
- samples/          Sample inputs and expected outputs
- comparators/      Comparison logic (programmatic + LLM-as-judge)
- runners/          Execute prompts and collect results
- reports/          Generated comparison reports

Usage:
    # Run benchmark for a specific agent
    python -m dev_harness.run profile_extraction

    # Run with specific prompt version
    python -m dev_harness.run profile_extraction --prompt v2_concise

    # Compare two prompt versions
    python -m dev_harness.compare profile_extraction v1_original v2_concise
"""

from .comparators import StructuredComparator, LLMJudgeComparator
from .runners import run_prompt_benchmark, compare_prompts

__all__ = [
    "StructuredComparator",
    "LLMJudgeComparator",
    "run_prompt_benchmark",
    "compare_prompts",
]
