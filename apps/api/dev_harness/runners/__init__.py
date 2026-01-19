"""Benchmark runners for prompt testing.

Main functions:
- run_prompt_benchmark: Run a prompt against all samples, produce report
- compare_prompts: Compare two prompt versions head-to-head
"""

import json
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from ..samples import load_sample, list_samples, SAMPLES_DIR
from ..comparators import StructuredComparator, LLMJudgeComparator


@dataclass
class BenchmarkResult:
    """Result from running a benchmark."""
    prompt_version: str
    model: str
    sample_id: str
    input_text: str
    expected: dict
    actual: dict
    latency_ms: float
    comparison_report: dict
    timestamp: str


@dataclass
class BenchmarkSummary:
    """Summary of benchmark run across all samples."""
    prompt_version: str
    model: str
    total_samples: int
    avg_score: float
    avg_latency_ms: float
    pass_count: int  # Samples with score >= 95%
    fail_count: int
    results: list[BenchmarkResult]

    def summary(self) -> str:
        """Human-readable summary."""
        lines = [
            f"\n{'='*60}",
            f"BENCHMARK: {self.prompt_version} ({self.model})",
            f"{'='*60}",
            f"Samples: {self.pass_count}/{self.total_samples} passed (>= 95%)",
            f"Avg Score: {self.avg_score * 100:.1f}%",
            f"Avg Latency: {self.avg_latency_ms:.0f}ms",
            "",
        ]

        # Show failing samples
        failing = [r for r in self.results if r.comparison_report.get("overall_score", 0) < 0.95]
        if failing:
            lines.append("FAILING SAMPLES:")
            for r in failing:
                score = r.comparison_report.get("overall_score", 0) * 100
                lines.append(f"  - {r.sample_id}: {score:.1f}%")
                # Show top issues
                missing = r.comparison_report.get("missing_fields", [])[:3]
                if missing:
                    lines.append(f"    Missing: {missing}")

        return "\n".join(lines)

    def to_dict(self) -> dict:
        """Convert to dict for JSON."""
        return {
            "prompt_version": self.prompt_version,
            "model": self.model,
            "total_samples": self.total_samples,
            "avg_score": self.avg_score,
            "avg_latency_ms": self.avg_latency_ms,
            "pass_count": self.pass_count,
            "fail_count": self.fail_count,
            "results": [
                {
                    "sample_id": r.sample_id,
                    "latency_ms": r.latency_ms,
                    "comparison": r.comparison_report,
                }
                for r in self.results
            ],
        }


# Prompt configurations
PROMPTS = {
    "profile_extraction": {
        "v1_original": {
            "system": """You are an expert at extracting structured information from LinkedIn profiles.

Given the raw text content from a LinkedIn profile page, extract the following information in JSON format:

{
    "name": "Full name",
    "headline": "Professional headline",
    "summary": "About/summary section",
    "location": "Location",
    "experience": [
        {
            "company": "Company name",
            "position": "Job title",
            "location": "Location if available",
            "start_date": "Start date",
            "end_date": "End date or null if current",
            "is_current": true/false,
            "achievements": ["Achievement 1", "Achievement 2"],
            "technologies": ["Tech 1", "Tech 2"],
            "description": "Role description"
        }
    ],
    "education": [
        {
            "institution": "School name",
            "degree": "Degree type",
            "field_of_study": "Field",
            "start_date": "Start date",
            "end_date": "End date"
        }
    ],
    "skills": ["Skill 1", "Skill 2"],
    "certifications": ["Cert 1", "Cert 2"]
}

Extract as much information as available. If something is not present, omit the field or use null.
Be precise and don't make up information that isn't clearly stated in the profile.""",
            "user_template": "Extract profile information from:\n\n{input}"
        },
        "v2_concise": {
            "system": """Extract LinkedIn profile as JSON:
{name, headline, summary, location, experience[], education[], skills[], certifications[]}

experience[]: {company, position, location, start_date, end_date, is_current, achievements[], technologies[], description}
education[]: {institution, degree, field_of_study, start_date, end_date}

Precise extraction. Omit missing. JSON only.""",
            "user_template": "{input}"
        }
    },
    "job_extraction": {
        "v1_original": {
            "system": """You are an expert at extracting structured information from job postings.

Given the raw text content from a job posting page, extract the following information in JSON format:

{
    "title": "Job title",
    "company_name": "Company name",
    "description": "Full job description",
    "location": "Job location",
    "work_type": "remote/hybrid/onsite",
    "job_type": "full-time/part-time/contract",
    "experience_level": "Entry/Mid/Senior/Lead/Executive",
    "requirements": ["Required qualification 1", "Required qualification 2"],
    "preferred_qualifications": ["Nice to have 1", "Nice to have 2"],
    "responsibilities": ["Responsibility 1", "Responsibility 2"],
    "tech_stack": ["Technology 1", "Framework 2"],
    "benefits": ["Benefit 1", "Benefit 2"],
    "salary_range": "Salary range if mentioned"
}

Extract as much information as available. If something is not present, omit the field or use null.
For tech_stack, extract all mentioned programming languages, frameworks, tools, and platforms.""",
            "user_template": "Extract job posting information from:\n\n{input}"
        }
    }
}


def run_prompt(
    agent_type: str,
    prompt_version: str,
    input_text: str,
    model: str = "claude-3-haiku-20240307",
) -> tuple[dict, float]:
    """Run a single prompt and return output + latency.

    Args:
        agent_type: 'profile_extraction' or 'job_extraction'
        prompt_version: Version key from PROMPTS
        input_text: The raw input text
        model: Model to use

    Returns:
        (output_dict, latency_ms)
    """
    from langchain_anthropic import ChatAnthropic
    from langchain_core.messages import SystemMessage, HumanMessage
    from config import get_settings

    settings = get_settings()
    prompt_config = PROMPTS[agent_type][prompt_version]

    llm = ChatAnthropic(
        model=model,
        api_key=settings.anthropic_api_key,
        temperature=0,
    )

    messages = [
        SystemMessage(content=prompt_config["system"]),
        HumanMessage(content=prompt_config["user_template"].format(input=input_text)),
    ]

    start = time.perf_counter()
    response = llm.invoke(messages)
    latency_ms = (time.perf_counter() - start) * 1000

    # Parse JSON from response
    content = response.content
    if "```json" in content:
        content = content.split("```json")[1].split("```")[0]
    elif "```" in content:
        content = content.split("```")[1].split("```")[0]

    output = json.loads(content)
    return output, latency_ms


def run_prompt_benchmark(
    agent_type: str,
    prompt_version: str,
    model: str = "claude-3-haiku-20240307",
    use_llm_judge: bool = False,
    offline: bool = False,
) -> BenchmarkSummary:
    """Run benchmark for a prompt version against all samples.

    Args:
        agent_type: 'profile' or 'job'
        prompt_version: Prompt version to test
        model: Model to use
        use_llm_judge: Use LLM-as-judge instead of structured comparison
        offline: Skip actual LLM calls (use for testing)

    Returns:
        BenchmarkSummary with all results
    """
    # Map agent type to extraction type
    extraction_type = f"{agent_type}_extraction"

    sample_ids = list_samples(agent_type)
    if not sample_ids:
        raise ValueError(f"No samples found for agent type: {agent_type}")

    results = []
    comparator = StructuredComparator()
    llm_judge = LLMJudgeComparator() if use_llm_judge else None

    for sample_id in sample_ids:
        sample = load_sample(agent_type, sample_id)
        input_text = sample["input"]
        expected = sample["expected"]

        if offline:
            # Use expected as actual for testing
            actual = expected.copy()
            latency_ms = 0.0
        else:
            actual, latency_ms = run_prompt(
                extraction_type,
                prompt_version,
                input_text,
                model,
            )

        # Compare
        if use_llm_judge and llm_judge:
            verdict = llm_judge.judge(extraction_type, actual, expected)
            comparison = verdict.to_dict()
        else:
            report = comparator.compare(actual, expected)
            comparison = report.to_dict()

        results.append(BenchmarkResult(
            prompt_version=prompt_version,
            model=model,
            sample_id=sample_id,
            input_text=input_text[:500],  # Truncate for storage
            expected=expected,
            actual=actual,
            latency_ms=latency_ms,
            comparison_report=comparison,
            timestamp=datetime.now().isoformat(),
        ))

    # Calculate summary
    scores = [r.comparison_report.get("overall_score", 0) for r in results]
    latencies = [r.latency_ms for r in results]

    return BenchmarkSummary(
        prompt_version=prompt_version,
        model=model,
        total_samples=len(results),
        avg_score=sum(scores) / len(scores) if scores else 0,
        avg_latency_ms=sum(latencies) / len(latencies) if latencies else 0,
        pass_count=sum(1 for s in scores if s >= 0.95),
        fail_count=sum(1 for s in scores if s < 0.95),
        results=results,
    )


def compare_prompts(
    agent_type: str,
    version_a: str,
    version_b: str,
    model: str = "claude-3-haiku-20240307",
) -> dict:
    """Compare two prompt versions head-to-head.

    Returns comparison summary showing which performs better.
    """
    summary_a = run_prompt_benchmark(agent_type, version_a, model)
    summary_b = run_prompt_benchmark(agent_type, version_b, model)

    winner = version_a if summary_a.avg_score > summary_b.avg_score else version_b

    return {
        "winner": winner,
        "version_a": {
            "version": version_a,
            "avg_score": summary_a.avg_score,
            "avg_latency_ms": summary_a.avg_latency_ms,
            "pass_count": summary_a.pass_count,
        },
        "version_b": {
            "version": version_b,
            "avg_score": summary_b.avg_score,
            "avg_latency_ms": summary_b.avg_latency_ms,
            "pass_count": summary_b.pass_count,
        },
        "score_delta": summary_a.avg_score - summary_b.avg_score,
        "latency_delta_ms": summary_a.avg_latency_ms - summary_b.avg_latency_ms,
    }


def save_report(summary: BenchmarkSummary, output_dir: Path | None = None):
    """Save benchmark report to file."""
    if output_dir is None:
        output_dir = SAMPLES_DIR.parent / "reports"
    output_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{summary.prompt_version}_{timestamp}.json"

    with open(output_dir / filename, "w") as f:
        json.dump(summary.to_dict(), f, indent=2)

    return output_dir / filename
