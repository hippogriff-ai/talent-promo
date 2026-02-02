"""LLM-based grader for drafting stage outputs.

Uses an LLM-as-a-judge approach to evaluate resume drafts on 6 dimensions:
1. Source fidelity (25%) - claims traceable to original resume
2. Conciseness (15%) - bullet length, compound sentences, summary length
3. Narrative hierarchy (15%) - candidate's prominence preserved
4. Narrative coherence (15%) - clear through-line, not scattered keywords
5. Job relevance (20%) - top 3-5 requirements addressed deeply
6. ATS optimization (10%) - structure, keywords, parseability

This is used in the drafting prompt tuning loop to iteratively improve drafts.
"""

import json
import logging
from dataclasses import dataclass
from typing import Awaitable, Callable, Optional

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

logger = logging.getLogger(__name__)


GRADING_SYSTEM_PROMPT = """You are an expert resume reviewer, hiring manager, and recruiter with 15 years of experience.

You receive THREE inputs: a resume draft, a job posting, and the candidate's ORIGINAL resume/profile text.
Your job: evaluate whether this resume would get the candidate an interview, while sounding authentically human.

CONTEXT: 53% of hiring managers have reservations about AI-generated resumes. 33.5% spot them in under 20 seconds. Authenticity is now a competitive advantage. Your scoring must reflect this reality.

Score each dimension 0-100:

1. **SOURCE_FIDELITY** (weight: 25%): Cross-reference every claim against the original resume.
   - Score 0-40: Any fabricated metric (e.g., "10x improvement" not in source)
   - Score 41-70: Experience scopes conflated OR company scale attributed to individual
   - Score 71-85: Minor embellishments but fundamentally accurate
   - Score 86-100: All claims clearly traceable to source material
   Red flags (any of these = score ≤ 70):
   - Invented percentages or metrics not in source
   - Inflated scope or merged timeframes
   - Upgraded verbs ("helped" → "led", "contributed to" → "drove")
   - **SUMMARY YEAR+DOMAIN CONFLATION**: The summary says "N years [narrow domain]" but the source shows N years total career with only brief exposure to that domain. EXAMPLE: Source has 8yr SWE + 1yr AI work → summary says "8+ years building AI-powered products" = score ≤ 50.
   - **COMPANY-TO-INDIVIDUAL SCALE ATTRIBUTION**: Resume attributes the employer's scale to the candidate's individual work. EXAMPLE: Source says employer "serves 2M users" → resume says candidate is "serving 2M users" or "impacting millions" when the candidate's project scope was smaller = score ≤ 60.
   HOWEVER: If the source text explicitly states a metric as the candidate's own (e.g., "Shipped features used by 1M+ users"), the draft CAN use it. Only penalize when the draft invents or inflates scale NOT found in the source.
   CHECK THE SUMMARY FIRST — it's where conflation is most common and most visible to recruiters.
   EXAMPLE BAD: Source says "contributed to migration" → draft says "Led enterprise-wide migration"
   EXAMPLE BAD: Source shows 8yr SWE + 1yr AI → summary says "8+ years building AI products"
   EXAMPLE BAD: Employer serves millions → summary says "serving millions of legal professionals"
   EXAMPLE GOOD: Source says "reduced latency 40%" → draft says "Cut API latency 40%"
   EXAMPLE GOOD: Source has 8yr SWE + 1yr AI → summary says "Full-stack engineer with 8 years of software development. Shipped AI assistant from POC to production."

2. **CONCISENESS** (weight: 15%): Length enforcement AND human voice.
   Part A — Word counts:
   - Count words per bullet. Any bullet > 15 words = score below 60.
   - Compound sentences joining two achievements = penalty
   - Summary must be under 40 words
   Part B — AI-tell detection (equally important):
   - Deduct 5 points per occurrence of these AI-tell words/phrases:
     "delve", "leverage", "pivotal", "seamless", "holistic", "synergy", "robust",
     "streamline", "spearheaded", "orchestrated", "revolutionized", "utilize",
     "innovative", "cutting-edge", "dynamic", "passionate about"
   - Deduct 5 points for generic filler: "various", "multiple", "diverse range",
     "proven track record", "results-driven", "exceptional"
   - Deduct 3 points for uniform rhythm (every bullet same length/cadence)
   - Score 86-100: All bullets ≤ 12 words, zero AI-tells, varied rhythm
   - Score 71-85: All bullets ≤ 15 words, 0-1 AI-tells
   - Score below 60: Any bullet > 15 words OR 3+ AI-tells

3. **NARRATIVE_HIERARCHY** (weight: 15%): Preserves the candidate's story.
   - Is the candidate's most recent/prominent role still most prominent?
   - Is their lead achievement still in the top third?
   - Has the draft reordered to chase job keywords? (BAD)
   - Is seniority-appropriate? (entry-level shouldn't say "spearheaded cross-functional strategy")
   - Score 86-100: Original prominence fully preserved, seniority-appropriate
   - Score 71-85: Mostly preserved with minor reordering
   - Score below 60: Completely reordered to match posting, or seniority mismatch

4. **NARRATIVE_COHERENCE** (weight: 15%): Tells one clear story with authentic voice.
   Part A — Story integrity (does the resume answer "who IS this person?"):
   - Summary sets up a clear identity → experience bullets reinforce it → skills confirm it
   - Or is it scattered keyword coverage with no identity?
   - Test: Can you describe this candidate in one sentence after reading? If not, coherence is weak.
   Part B — Authenticity markers (count these — each one adds points):
   - Specific numbers WITH context (not "improved performance" but "from 3.2s to 0.8s") = +2
   - Trade-offs/constraints mentioned ("despite legacy codebase", "within 3-month deadline") = +3
   - Unique details only the candidate would know ("tool used by 23 team members daily") = +3
   - Technologies named specifically (not "various tools") = +1 per instance
   Part C — Authenticity penalties (count these — each one subtracts):
   - Generic phrases applicable to anyone = -5 each
   - "Results-driven professional with proven track record" type openings = -10
   - Every bullet following identical pattern without variation = -5
   SCORING METHOD (mandatory — do NOT skip this):
   Step 1: List every authenticity marker found (before/after context, constraints, unique details, named tools).
   Step 2: Check for generic phrases ("results-driven", "proven track record", etc.).
   Step 3: Assign score based on marker count:
     0 markers = 72 | 1 marker = 78 | 2 markers = 82 | 3 markers = 86
     4 markers = 89 | 5+ markers = 92 | With constraints/trade-offs: +3
   Subtract: -5 per generic phrase, -10 for "proven track record" opening, -5 for uniform rhythm.
   The score MUST reflect the marker count. Do NOT default to 85.

5. **JOB_RELEVANCE** (weight: 20%): Focused depth, not scattered breadth.
   - Are TOP 3-5 job requirements addressed with specific, deep evidence?
   - Does the resume use the job posting's EXACT technology names where the candidate has matching experience?
   - Does it use XYZ formula? "Accomplished [X] as measured by [Y] by doing [Z]"
   - Quantification: use source metrics when available; specific-but-unquantified is acceptable when source lacks numbers
   - NOT "all requirements superficially touched"
   SCORING GUIDE (reward focused specialists, penalize scattered generalists):
   - Score 86-100: 3-5 core requirements deeply addressed with named technologies + specific evidence. Unmatched requirements wisely omitted.
   - Score 78-85: Most core requirements addressed, some technology alignment, but evidence depth varies.
   - Score 70-77: Requirements addressed but shallowly — vague language, no specific evidence.
   - Score below 60: Superficial keyword scattering, bullets that name a skill without evidence, OR fabricated experience to fill gaps.
   IMPORTANT: Don't penalize for lack of quantification when the source material has few numbers.
   Instead, reward SPECIFICITY — naming exact technologies, tools, and methods from the source.
   IMPORTANT: When a candidate only matches 3-4 of 8+ requirements, a resume that deeply addresses those 3-4 and ignores the rest should score 80+. Don't penalize for honest gaps — penalize for shallow coverage of non-matching requirements.
   EXAMPLE BAD: "Experienced in cloud computing and DevOps practices" (vague, no specifics)
   EXAMPLE BAD: Mentioning GraphQL in a bullet when the source never mentions GraphQL (fabrication to match requirements)
   EXAMPLE GOOD: "Cut deploy time from 2hr to 15min using GitHub Actions + Docker" (source metric + job tech)
   EXAMPLE GOOD: "Built caching layer with Redis for product search API" (specific, named tech, no metric needed)
   EXAMPLE GOOD: Ignoring 6 non-matching requirements to deeply address 4 matching ones = focused specialist

6. **ATS_OPTIMIZATION** (weight: 10%): Structure for machine parsing.
   - Clean HTML (h1, h2, h3, ul/li, p — no tables, images, complex formatting)
   - Standard headers: "Experience", "Education", "Skills" (not "My Journey" or creative alternatives)
   - Keywords naturally included, not stuffed (2-3% density max)
   - Skills grouped by category (Languages: X, Y | Frameworks: A, B) not flat comma-separated lists
   - Reverse-chronological order in Experience section
   - 3-5 bullets per role, most recent role gets most detail

Respond ONLY with valid JSON:
{
    "source_fidelity": <score>,
    "conciseness": <score>,
    "narrative_hierarchy": <score>,
    "narrative_coherence": <score>,
    "job_relevance": <score>,
    "ats_optimization": <score>,
    "overall_score": <weighted average using weights above>,
    "strengths": ["strength 1", "strength 2"],
    "weaknesses": ["weakness 1", "weakness 2"],
    "specific_improvements": ["improvement 1", "improvement 2", "improvement 3"],
    "reasoning": "Brief explanation with specific examples from the resume"
}"""


@dataclass
class DraftLLMGrade:
    """Grade from LLM evaluation with 6 dimensions."""
    source_fidelity: float
    conciseness: float
    narrative_hierarchy: float
    narrative_coherence: float
    job_relevance: float
    ats_optimization: float
    overall_score: float
    strengths: list[str]
    weaknesses: list[str]
    specific_improvements: list[str]
    reasoning: str


# Weights for computing the overall score
DIMENSION_WEIGHTS = {
    "source_fidelity": 0.25,
    "conciseness": 0.15,
    "narrative_hierarchy": 0.15,
    "narrative_coherence": 0.15,
    "job_relevance": 0.20,
    "ats_optimization": 0.10,
}


class DraftingLLMGrader:
    """LLM-based grader for resume drafts.

    Uses Claude as a judge to evaluate draft quality across 6 dimensions.
    """

    def __init__(self, model: str = "claude-sonnet-4-20250514"):
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
        original_resume_text: str = "",
        discovered_experiences: list | None = None,
    ) -> DraftLLMGrade:
        """Grade a resume draft using LLM.

        Args:
            draft_html: The HTML content of the resume draft.
            job_posting: The target job posting dict.
            user_profile: The user's profile dict.
            original_resume_text: The candidate's original resume/profile text
                for cross-referencing claims (source fidelity).
            discovered_experiences: Additional experiences from discovery phase.

        Returns:
            DraftLLMGrade with scores and feedback.
        """
        llm = self._get_llm()

        job_summary = self._summarize_job(job_posting)
        profile_summary = self._summarize_profile(user_profile)

        # Build original source section for fidelity checking
        source_section = ""
        if original_resume_text:
            source_section = f"""## Original Resume/Profile Text (use this to verify claims)
{original_resume_text[:5000]}

"""
        if discovered_experiences:
            exp_text = "\n".join(
                f"- {e.get('description', '')}" for e in discovered_experiences
            )
            source_section += f"""## Discovered Experiences (additional verified info)
{exp_text}

"""

        evaluation_prompt = f"""Evaluate this resume draft:

## Target Job
{job_summary}

## Candidate Background
{profile_summary}

{source_section}## Resume Draft
```html
{draft_html}
```

Cross-reference the draft against the original resume text. Flag any claims not traceable to source.
PAY SPECIAL ATTENTION to the Professional Summary — check if years+domain claims match actual experience duration in that domain, and if scale claims (serving millions, at scale) are the candidate's own work scope or the employer's.
For JOB_RELEVANCE: when the source lacks many hard metrics, reward specificity through named technologies, concrete project descriptions, and skills alignment — don't penalize for missing quantification that isn't in the source material.
Provide your evaluation as JSON."""

        messages = [
            SystemMessage(content=GRADING_SYSTEM_PROMPT),
            HumanMessage(content=evaluation_prompt),
        ]

        response = await llm.ainvoke(messages)

        try:
            content = response.content
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]

            data = json.loads(content)

            # Compute weighted overall if LLM didn't
            scores = {
                "source_fidelity": data.get("source_fidelity", 50),
                "conciseness": data.get("conciseness", 50),
                "narrative_hierarchy": data.get("narrative_hierarchy", 50),
                "narrative_coherence": data.get("narrative_coherence", 50),
                "job_relevance": data.get("job_relevance", 50),
                "ats_optimization": data.get("ats_optimization", 50),
            }
            weighted = sum(
                scores[dim] * DIMENSION_WEIGHTS[dim]
                for dim in DIMENSION_WEIGHTS
            )

            return DraftLLMGrade(
                source_fidelity=scores["source_fidelity"],
                conciseness=scores["conciseness"],
                narrative_hierarchy=scores["narrative_hierarchy"],
                narrative_coherence=scores["narrative_coherence"],
                job_relevance=scores["job_relevance"],
                ats_optimization=scores["ats_optimization"],
                overall_score=round(weighted, 1),
                strengths=data.get("strengths", []),
                weaknesses=data.get("weaknesses", []),
                specific_improvements=data.get("specific_improvements", []),
                reasoning=data.get("reasoning", ""),
            )
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Failed to parse grading response: {e}")
            return DraftLLMGrade(
                source_fidelity=50,
                conciseness=50,
                narrative_hierarchy=50,
                narrative_coherence=50,
                job_relevance=50,
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
        draft_generator: Callable[[dict, dict, str], Awaitable[str]],
    ) -> dict:
        """Grade a batch of samples.

        Args:
            samples: List of sample dicts with profile, job, and optional
                profile_text and expected output.
            draft_generator: Async function that takes (profile, job) and
                returns draft HTML.

        Returns:
            Batch result with average score and individual results.
        """
        results = []

        for sample in samples:
            try:
                draft_html = await draft_generator(
                    sample["profile"],
                    sample["job"],
                    sample.get("profile_text", ""),
                )

                grade = await self.grade(
                    draft_html=draft_html,
                    job_posting=sample["job"],
                    user_profile=sample["profile"],
                    original_resume_text=sample.get("profile_text", ""),
                    discovered_experiences=sample.get("discovered_experiences"),
                )

                results.append({
                    "sample_id": sample.get("id", "unknown"),
                    "grade": {
                        "source_fidelity": grade.source_fidelity,
                        "conciseness": grade.conciseness,
                        "narrative_hierarchy": grade.narrative_hierarchy,
                        "narrative_coherence": grade.narrative_coherence,
                        "job_relevance": grade.job_relevance,
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

        valid_scores = [
            r["grade"]["overall_score"]
            for r in results
            if "error" not in r.get("grade", {})
        ]
        avg_score = sum(valid_scores) / len(valid_scores) if valid_scores else 0

        all_improvements = []
        for r in results:
            all_improvements.extend(r.get("improvements", []))

        improvement_counts: dict[str, int] = {}
        for imp in all_improvements:
            improvement_counts[imp] = improvement_counts.get(imp, 0) + 1

        top_suggestions = sorted(
            improvement_counts.items(), key=lambda x: -x[1]
        )[:5]

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
