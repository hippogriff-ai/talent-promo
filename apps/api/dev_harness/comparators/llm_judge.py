"""LLM-as-judge comparison for subjective evaluations.

Used when:
1. Output quality is subjective (e.g., resume writing quality)
2. Semantic equivalence matters more than exact matching
3. Evaluating gap analysis insights
"""

import json
from dataclasses import dataclass
from typing import Any


@dataclass
class JudgeVerdict:
    """LLM judge evaluation result."""
    overall_score: float  # 0.0 - 1.0
    reasoning: str
    dimension_scores: dict[str, float]
    strengths: list[str]
    weaknesses: list[str]

    def summary(self) -> str:
        """Human-readable summary."""
        lines = [
            f"Overall Score: {self.overall_score * 100:.1f}%",
            f"\nDimensions:",
        ]
        for dim, score in self.dimension_scores.items():
            lines.append(f"  {dim}: {score * 100:.1f}%")

        if self.strengths:
            lines.append(f"\nStrengths:")
            for s in self.strengths:
                lines.append(f"  + {s}")

        if self.weaknesses:
            lines.append(f"\nWeaknesses:")
            for w in self.weaknesses:
                lines.append(f"  - {w}")

        lines.append(f"\nReasoning: {self.reasoning}")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "overall_score": self.overall_score,
            "reasoning": self.reasoning,
            "dimension_scores": self.dimension_scores,
            "strengths": self.strengths,
            "weaknesses": self.weaknesses,
        }


# Evaluation prompts for different tasks
JUDGE_PROMPTS = {
    "profile_extraction": """You are evaluating a LinkedIn profile extraction.

EXPECTED OUTPUT (ground truth):
{expected}

ACTUAL OUTPUT (to evaluate):
{actual}

Evaluate on these dimensions (0-100 each):
1. completeness: Are all important fields extracted?
2. accuracy: Are extracted values correct?
3. structure: Is the data properly structured?
4. detail: Are achievements/technologies captured?

Return JSON:
{{
  "overall_score": <0-100>,
  "dimensions": {{
    "completeness": <0-100>,
    "accuracy": <0-100>,
    "structure": <0-100>,
    "detail": <0-100>
  }},
  "strengths": ["strength1", "strength2"],
  "weaknesses": ["weakness1", "weakness2"],
  "reasoning": "Brief explanation"
}}""",

    "job_extraction": """You are evaluating a job posting extraction.

EXPECTED OUTPUT (ground truth):
{expected}

ACTUAL OUTPUT (to evaluate):
{actual}

Evaluate on these dimensions (0-100 each):
1. completeness: Are title, company, requirements captured?
2. accuracy: Are extracted values correct?
3. tech_stack: Is the technology list comprehensive?
4. requirements: Are requirements properly separated from nice-to-haves?

Return JSON:
{{
  "overall_score": <0-100>,
  "dimensions": {{
    "completeness": <0-100>,
    "accuracy": <0-100>,
    "tech_stack": <0-100>,
    "requirements": <0-100>
  }},
  "strengths": ["strength1", "strength2"],
  "weaknesses": ["weakness1", "weakness2"],
  "reasoning": "Brief explanation"
}}""",

    "gap_analysis": """You are evaluating a resume-job gap analysis.

PROFILE:
{profile}

JOB:
{job}

EXPECTED ANALYSIS:
{expected}

ACTUAL ANALYSIS:
{actual}

Evaluate on these dimensions (0-100 each):
1. strength_identification: Are real strengths identified?
2. gap_identification: Are actual gaps found?
3. actionability: Are recommendations actionable?
4. relevance: Do insights connect profile to job?

Return JSON:
{{
  "overall_score": <0-100>,
  "dimensions": {{
    "strength_identification": <0-100>,
    "gap_identification": <0-100>,
    "actionability": <0-100>,
    "relevance": <0-100>
  }},
  "strengths": ["strength1", "strength2"],
  "weaknesses": ["weakness1", "weakness2"],
  "reasoning": "Brief explanation"
}}"""
}


class LLMJudgeComparator:
    """Use LLM as judge for subjective evaluations."""

    def __init__(self, llm=None):
        """
        Args:
            llm: LangChain LLM instance. If None, uses default Anthropic.
        """
        self.llm = llm

    def _get_llm(self):
        """Get or create LLM instance."""
        if self.llm:
            return self.llm

        from langchain_anthropic import ChatAnthropic
        from config import get_settings
        settings = get_settings()
        return ChatAnthropic(
            model="claude-3-haiku-20240307",  # Fast + cheap for judging
            api_key=settings.anthropic_api_key,
            temperature=0,
        )

    def judge(
        self,
        task_type: str,
        actual: dict,
        expected: dict,
        context: dict | None = None,
    ) -> JudgeVerdict:
        """Have LLM judge the extraction quality.

        Args:
            task_type: 'profile_extraction', 'job_extraction', or 'gap_analysis'
            actual: The actual output to evaluate
            expected: The expected output (ground truth)
            context: Additional context (e.g., profile/job for gap analysis)

        Returns:
            JudgeVerdict with scores and feedback
        """
        if task_type not in JUDGE_PROMPTS:
            raise ValueError(f"Unknown task type: {task_type}")

        # Build prompt
        prompt_template = JUDGE_PROMPTS[task_type]

        format_args = {
            "actual": json.dumps(actual, indent=2),
            "expected": json.dumps(expected, indent=2),
        }
        if context:
            format_args.update(context)

        prompt = prompt_template.format(**format_args)

        # Call LLM
        llm = self._get_llm()
        response = llm.invoke(prompt)

        # Parse response
        return self._parse_verdict(response.content)

    def _parse_verdict(self, response: str) -> JudgeVerdict:
        """Parse LLM response into JudgeVerdict."""
        try:
            # Extract JSON from response
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                json_str = response.split("```")[1].split("```")[0]
            else:
                json_str = response

            data = json.loads(json_str)

            return JudgeVerdict(
                overall_score=data.get("overall_score", 0) / 100,
                reasoning=data.get("reasoning", ""),
                dimension_scores={
                    k: v / 100 for k, v in data.get("dimensions", {}).items()
                },
                strengths=data.get("strengths", []),
                weaknesses=data.get("weaknesses", []),
            )
        except (json.JSONDecodeError, KeyError) as e:
            # Return low score if parsing fails
            return JudgeVerdict(
                overall_score=0.0,
                reasoning=f"Failed to parse LLM response: {e}",
                dimension_scores={},
                strengths=[],
                weaknesses=[f"Parse error: {response[:200]}"],
            )

    def judge_offline(
        self,
        task_type: str,
        actual: dict,
        expected: dict,
    ) -> JudgeVerdict:
        """Offline judging using structured comparison as fallback.

        Used when LLM is not available (testing, CI, etc.)
        """
        from .structured import StructuredComparator

        comparator = StructuredComparator()
        report = comparator.compare(actual, expected)

        return JudgeVerdict(
            overall_score=report.overall_score,
            reasoning=f"Offline comparison: {report.matched_fields}/{report.total_fields} fields matched",
            dimension_scores={
                "completeness": 1.0 - (len(report.missing_fields) / max(report.total_fields, 1)),
                "accuracy": report.overall_score,
            },
            strengths=[f"Matched {report.matched_fields} fields"],
            weaknesses=[f"Missing: {f}" for f in report.missing_fields[:5]],
        )
