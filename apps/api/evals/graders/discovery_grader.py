"""Discovery Question Quality Grader.

Evaluates discovery prompts on their ability to elicit hidden, valuable experiences
from users that will resonate with hiring managers.

Uses LLM-as-a-judge pattern to score questions on multiple dimensions.
"""

import json
import logging
from typing import TypedDict, Optional, Callable, Awaitable
from collections import Counter

import anthropic

logger = logging.getLogger(__name__)


class DimensionScores(TypedDict):
    """Scores for each evaluation dimension."""
    strength_to_gap_bridge: float
    conversational_agility: float
    executive_coach_voice: float
    hidden_value_finder: float
    specificity_context: float


class DiscoveryGradeResult(TypedDict):
    """Result from grading a set of discovery questions."""
    overall_score: float  # 0-100
    dimension_scores: DimensionScores
    reasoning: str
    best_question: str
    worst_question: str
    suggestions: list[str]


class BatchGradeResult(TypedDict):
    """Result from grading a batch of samples."""
    average_score: float
    individual_results: list[dict]
    improvement_suggestions: list[str]


GRADING_PROMPT = '''You are evaluating AI-generated discovery questions for a resume optimization tool.

## Core Philosophy
**Strength-first, not deficit-first.** Never make the candidate feel like they're missing something. Instead:
- "Your experience with X is actually perfect for Y" (bridge building)
- "What you did at Company was more impressive than you realize" (value amplification)
- NOT: "You're missing leadership experience, tell me about leadership" (deficit focus)

The goal is to help job seekers see bridges from their existing strengths to job requirements,
uncover hidden value they didn't realize they had, and move conversations forward efficiently.

## Evaluation Dimensions (score each 0-100):

### 1. Strength-to-Gap Bridge (30%) - HIGHEST WEIGHT
Does the question help them see how their EXISTING experience connects to job requirements?
- Frames gaps as bridges to build, not deficits to fill
- Makes them feel empowered, not lacking
- Shows how their current skills/experiences are MORE relevant than they thought
- Connects dots they didn't see

Score High: "Your 3 years of agency work means you've seen dozens of codebases - that's exactly the adaptability Staff engineers need. When did jumping into unfamiliar code feel natural vs terrifying?"
Score High: "At DataCorp you built APIs that others consumed - that's half of full-stack already. Did you ever see the frontend struggling with your API design?"
Score Low: "You don't have frontend experience - have you tried React?" (deficit-focused)
Score Low: "Tell me about any leadership experience you might have" (assumes lacking)

### 2. Conversational Agility (20%)
Does the question/approach recognize when to dig deeper vs pivot fast?
- Gets to value quickly - no meandering warmups
- Questions should be concise (1-2 sentences max)
- Built-in pivot points: "If that doesn't ring a bell, think about..."
- NOT over-explaining before asking

Score High: Concise questions that can branch naturally
Score High: Questions with escape hatches ("If that's not ringing a bell...")
Score Low: Third question on the same topic when previous answers were thin
Score Low: Long, complex questions with 3+ sentences of setup

### 3. Executive Coach Voice (20%)
Does it feel like a senior mentor who sees potential in them?
Pattern: Affirm what they've done → Show why it's more valuable than they think → Probe for the story

Score High: "Managing patient handoffs in a hospital - that's basically incident response in tech. What made the difference between a smooth handoff and a dangerous one?"
Score High: "Completed sprint tickets for 2 years - but I bet some of those tickets had you debugging for hours. What's a bug that made you feel like a detective?"
Score Low: "Tell me about a time you demonstrated leadership" (cold interview style)

### 4. Hidden Value Finder (20%)
Surfaces experiences they might overlook or undervalue.
- Helps them see themselves through a hiring manager's eyes
- Reframes "just part of the job" as resume-worthy achievements
- Finds the story behind boring bullet points

Score High: "You 'fixed bugs' - but was there ever a bug that took you down a rabbit hole and taught you something unexpected about the system?"
Score High: "What's something you built that you're secretly proud of - even if it seemed too small for your resume?"
Score Low: "What are your main responsibilities?" (resume regurgitation)

### 5. Specificity & Context (10%)
Uses concrete details from their profile to make questions feel personal.
REQUIRED: Must reference specific details (company names, roles, achievements)

Score High: "At TechCorp when you built microservices..." (names their company)
Score High: "Growing DAU 3x at StartupXYZ..." (references their achievement)
Score Low: "Have you ever optimized performance?" (no context, generic)

## Anti-patterns (deduct points):
- Deficit framing: "You're missing X - tell me about X" (-20)
- Interview-style: "Tell me about a time when..." (-15)
- Over-lingering: Third question on exhausted topic (-15)
- Generic/non-specific: could apply to anyone (-15)
- Yes/no questions: don't invite storytelling (-15)
- No profile context: don't reference their experience (-15)
- Long-winded setup: 3+ sentences before the question (-10)

## Input:
User Profile: {user_profile}
Job Posting: {job_posting}
Gap Analysis: {gap_analysis}

Generated Questions: {generated_questions}

Gold Standard Examples (for reference): {gold_examples}
Anti-Pattern Examples (avoid these): {anti_patterns}

## Output JSON:
Return ONLY valid JSON with this structure:
{{
  "overall_score": <0-100, weighted: strength_to_gap_bridge*0.30 + conversational_agility*0.20 + executive_coach_voice*0.20 + hidden_value_finder*0.20 + specificity_context*0.10>,
  "dimension_scores": {{
    "strength_to_gap_bridge": <0-100>,
    "conversational_agility": <0-100>,
    "executive_coach_voice": <0-100>,
    "hidden_value_finder": <0-100>,
    "specificity_context": <0-100>
  }},
  "reasoning": "<2-3 sentences explaining the score - focus on bridge-building and conversational efficiency>",
  "best_question": "<which generated question was best and why - focus on strength-based framing>",
  "worst_question": "<which generated question was worst and why - focus on deficit framing or over-lingering>",
  "suggestions": [
    "<specific suggestion to improve - prioritize bridge-building and conciseness>",
    "<another specific suggestion>"
  ]
}}'''


class DiscoveryGrader:
    """Grades discovery questions using LLM-as-a-judge pattern."""

    def __init__(self, client: Optional[anthropic.Anthropic] = None):
        """Initialize grader with Anthropic client.

        Args:
            client: Anthropic client instance. If None, creates one from env.
        """
        self.client = client or anthropic.Anthropic()

    async def grade(
        self,
        sample: dict,
        generated_questions: list[str]
    ) -> DiscoveryGradeResult:
        """Grade generated discovery questions against a sample.

        Args:
            sample: Sample from the silver dataset with expected qualities.
            generated_questions: List of questions generated by the discovery agent.

        Returns:
            DiscoveryGradeResult with scores and suggestions.
        """
        prompt = GRADING_PROMPT.format(
            user_profile=json.dumps(sample["input"]["user_profile"], indent=2),
            job_posting=json.dumps(sample["input"]["job_posting"], indent=2),
            gap_analysis=json.dumps(sample["input"]["gap_analysis"], indent=2),
            generated_questions=json.dumps(generated_questions, indent=2),
            gold_examples=json.dumps(sample["gold_question_examples"], indent=2),
            anti_patterns=json.dumps(sample["anti_patterns"], indent=2),
        )

        # Use sync client with run_in_executor for async compatibility
        import asyncio
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1000,
                messages=[{"role": "user", "content": prompt}]
            )
        )

        # Parse JSON from response
        response_text = response.content[0].text
        try:
            # Try to extract JSON from response
            if "```json" in response_text:
                json_str = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                json_str = response_text.split("```")[1].split("```")[0]
            else:
                json_str = response_text
            result = json.loads(json_str.strip())
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse grading response: {e}")
            logger.error(f"Response text: {response_text}")
            # Return a default low score on parse failure
            result = {
                "overall_score": 0,
                "dimension_scores": {
                    "strength_to_gap_bridge": 0,
                    "conversational_agility": 0,
                    "executive_coach_voice": 0,
                    "hidden_value_finder": 0,
                    "specificity_context": 0
                },
                "reasoning": f"Parse error: {e}",
                "best_question": "N/A",
                "worst_question": "N/A",
                "suggestions": ["Fix grading prompt response format"]
            }

        return result

    async def grade_batch(
        self,
        samples: list[dict],
        question_generator: Callable[[dict], Awaitable[list[str]]]
    ) -> BatchGradeResult:
        """Grade a batch of samples and return aggregate metrics.

        Args:
            samples: List of samples from the silver dataset.
            question_generator: Async function that takes sample input and returns questions.

        Returns:
            BatchGradeResult with average score and individual results.
        """
        results = []
        for sample in samples:
            logger.info(f"Grading sample: {sample['id']}")
            questions = await question_generator(sample["input"])
            grade = await self.grade(sample, questions)
            results.append({
                "sample_id": sample["id"],
                "description": sample["description"],
                "questions": questions,
                "grade": grade
            })

        # Aggregate scores
        if results:
            avg_score = sum(r["grade"]["overall_score"] for r in results) / len(results)
        else:
            avg_score = 0

        return {
            "average_score": avg_score,
            "individual_results": results,
            "improvement_suggestions": self._aggregate_suggestions(results)
        }

    def _aggregate_suggestions(self, results: list[dict]) -> list[str]:
        """Find common suggestions across all samples.

        Args:
            results: List of grading results with suggestions.

        Returns:
            Top 5 most common suggestions.
        """
        all_suggestions = []
        for r in results:
            if "suggestions" in r["grade"]:
                all_suggestions.extend(r["grade"]["suggestions"])
        # Return unique suggestions, most common first
        return [s for s, _ in Counter(all_suggestions).most_common(5)]
