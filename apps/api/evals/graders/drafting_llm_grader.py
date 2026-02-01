"""LLM-based grader for drafting stage outputs.

Uses an LLM-as-a-judge approach to evaluate resume drafts on:
1. Relevance to job posting (does it address key requirements?)
2. Achievement clarity (are accomplishments specific and impactful?)
3. Professional quality (tone, grammar, formatting)
4. ATS optimization (keywords, structure)

This is used in the drafting prompt tuning loop to iteratively improve drafts.
"""

import json
import logging
from dataclasses import dataclass
from typing import Optional

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

logger = logging.getLogger(__name__)


GRADING_SYSTEM_PROMPT = """You are an expert resume reviewer and hiring manager.
Your task is to evaluate resume drafts and provide structured feedback.

Evaluate the resume on these dimensions (score each 0-100):

1. **JOB_RELEVANCE** (0-100): How well does the resume address the specific job requirements?
   - Are required skills highlighted?
   - Does experience align with responsibilities?
   - Are keywords from the job posting naturally integrated?

2. **ACHIEVEMENT_QUALITY** (0-100): How strong are the accomplishments?
   - Are achievements specific and quantified where possible?
   - Do they demonstrate impact (numbers, percentages, scale)?
   - Are they relevant to the target role?

3. **PROFESSIONAL_QUALITY** (0-100): How polished is the writing?
   - Is the tone appropriate (professional but not stiff)?
   - Are bullet points concise and action-oriented?
   - Is grammar and formatting consistent?

4. **ATS_OPTIMIZATION** (0-100): How well optimized for applicant tracking systems?
   - Are job keywords naturally included?
   - Is the structure clean and parseable?
   - Does it avoid problematic formatting (tables, images)?

Respond ONLY with valid JSON in this exact format:
{
    "job_relevance": <score>,
    "achievement_quality": <score>,
    "professional_quality": <score>,
    "ats_optimization": <score>,
    "overall_score": <weighted average>,
    "strengths": ["strength 1", "strength 2"],
    "weaknesses": ["weakness 1", "weakness 2"],
    "specific_improvements": ["improvement 1", "improvement 2", "improvement 3"],
    "reasoning": "Brief explanation of the scores"
}"""


@dataclass
class DraftLLMGrade:
    """Grade from LLM evaluation."""
    job_relevance: float
    achievement_quality: float
    professional_quality: float
    ats_optimization: float
    overall_score: float
    strengths: list[str]
    weaknesses: list[str]
    specific_improvements: list[str]
    reasoning: str


class DraftingLLMGrader:
    """LLM-based grader for resume drafts.

    Uses Claude as a judge to evaluate draft quality.
    """

    def __init__(self, model: str = "claude-sonnet-4-20250514"):
        """Initialize the grader.

        Args:
            model: Anthropic model to use for grading.
        """
        self.model = model
        self._llm: Optional[ChatAnthropic] = None

    def _get_llm(self) -> ChatAnthropic:
        """Get or create LLM instance."""
        if self._llm is None:
            from config import get_settings
            settings = get_settings()
            self._llm = ChatAnthropic(
                model=self.model,
                api_key=settings.anthropic_api_key,
                temperature=0,
            )
        return self._llm

    async def grade(
        self,
        draft_html: str,
        job_posting: dict,
        user_profile: dict,
    ) -> DraftLLMGrade:
        """Grade a resume draft using LLM.

        Args:
            draft_html: The HTML content of the resume draft.
            job_posting: The target job posting dict.
            user_profile: The user's profile dict.

        Returns:
            DraftLLMGrade with scores and feedback.
        """
        llm = self._get_llm()

        # Build evaluation context
        job_summary = self._summarize_job(job_posting)
        profile_summary = self._summarize_profile(user_profile)

        evaluation_prompt = f"""Evaluate this resume draft:

## Target Job
{job_summary}

## Candidate Background
{profile_summary}

## Resume Draft
```html
{draft_html}
```

Provide your evaluation as JSON."""

        messages = [
            SystemMessage(content=GRADING_SYSTEM_PROMPT),
            HumanMessage(content=evaluation_prompt),
        ]

        response = await llm.ainvoke(messages)

        # Parse response
        try:
            content = response.content
            # Handle code blocks
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]

            data = json.loads(content)

            return DraftLLMGrade(
                job_relevance=data.get("job_relevance", 50),
                achievement_quality=data.get("achievement_quality", 50),
                professional_quality=data.get("professional_quality", 50),
                ats_optimization=data.get("ats_optimization", 50),
                overall_score=data.get("overall_score", 50),
                strengths=data.get("strengths", []),
                weaknesses=data.get("weaknesses", []),
                specific_improvements=data.get("specific_improvements", []),
                reasoning=data.get("reasoning", ""),
            )
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Failed to parse grading response: {e}")
            # Return default grade on parse error
            return DraftLLMGrade(
                job_relevance=50,
                achievement_quality=50,
                professional_quality=50,
                ats_optimization=50,
                overall_score=50,
                strengths=[],
                weaknesses=["Failed to parse LLM response"],
                specific_improvements=[],
                reasoning=f"Parse error: {str(e)}",
            )

    async def grade_batch(
        self,
        samples: list[dict],
        draft_generator: callable,
    ) -> dict:
        """Grade a batch of samples.

        Args:
            samples: List of sample dicts with profile, job, and optional expected output.
            draft_generator: Async function that takes (profile, job) and returns draft HTML.

        Returns:
            Batch result with average score and individual results.
        """
        results = []

        for sample in samples:
            try:
                # Generate draft
                draft_html = await draft_generator(
                    sample["profile"],
                    sample["job"],
                )

                # Grade the draft
                grade = await self.grade(
                    draft_html=draft_html,
                    job_posting=sample["job"],
                    user_profile=sample["profile"],
                )

                results.append({
                    "sample_id": sample.get("id", "unknown"),
                    "grade": {
                        "job_relevance": grade.job_relevance,
                        "achievement_quality": grade.achievement_quality,
                        "professional_quality": grade.professional_quality,
                        "ats_optimization": grade.ats_optimization,
                        "overall_score": grade.overall_score,
                        "reasoning": grade.reasoning,
                    },
                    "improvements": grade.specific_improvements,
                })
            except Exception as e:
                logger.error(f"Error grading sample {sample.get('id')}: {e}")
                results.append({
                    "sample_id": sample.get("id", "unknown"),
                    "grade": {"overall_score": 0, "error": str(e)},
                    "improvements": [],
                })

        # Calculate average
        valid_scores = [r["grade"]["overall_score"] for r in results if "error" not in r["grade"]]
        avg_score = sum(valid_scores) / len(valid_scores) if valid_scores else 0

        # Aggregate improvement suggestions
        all_improvements = []
        for r in results:
            all_improvements.extend(r.get("improvements", []))

        # Deduplicate and rank suggestions
        improvement_counts = {}
        for imp in all_improvements:
            improvement_counts[imp] = improvement_counts.get(imp, 0) + 1

        top_suggestions = sorted(improvement_counts.items(), key=lambda x: -x[1])[:5]

        return {
            "average_score": avg_score,
            "individual_results": results,
            "improvement_suggestions": [s[0] for s in top_suggestions],
        }

    def _summarize_job(self, job: dict) -> str:
        """Create a summary of the job posting for evaluation context."""
        parts = []
        if title := job.get("title"):
            parts.append(f"**Title:** {title}")
        if company := job.get("company_name"):
            parts.append(f"**Company:** {company}")
        if reqs := job.get("requirements"):
            parts.append(f"**Key Requirements:** {', '.join(reqs[:5])}")
        if tech := job.get("tech_stack"):
            parts.append(f"**Tech Stack:** {', '.join(tech[:5])}")
        if resp := job.get("responsibilities"):
            parts.append(f"**Responsibilities:** {', '.join(resp[:3])}")
        return "\n".join(parts) if parts else "No job details provided"

    def _summarize_profile(self, profile: dict) -> str:
        """Create a summary of the user profile for evaluation context."""
        parts = []
        if name := profile.get("name"):
            parts.append(f"**Name:** {name}")
        if headline := profile.get("headline"):
            parts.append(f"**Headline:** {headline}")
        if exp := profile.get("experience"):
            companies = [e.get("company", "Unknown") for e in exp[:3]]
            parts.append(f"**Recent Companies:** {', '.join(companies)}")
        if skills := profile.get("skills"):
            parts.append(f"**Skills:** {', '.join(skills[:10])}")
        return "\n".join(parts) if parts else "No profile details provided"
