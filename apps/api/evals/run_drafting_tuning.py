#!/usr/bin/env python3
"""CLI for running the drafting prompt tuning loop with memory.

Usage:
    cd apps/api && python -m evals.run_drafting_tuning --check        # Check current status
    cd apps/api && python -m evals.run_drafting_tuning --iterate      # Run one iteration
    cd apps/api && python -m evals.run_drafting_tuning --reset        # Reset history (keeps memory)
    cd apps/api && python -m evals.run_drafting_tuning --show-memory  # Show accumulated learnings
    cd apps/api && python -m evals.run_drafting_tuning --reset-memory # Reset memory learnings

The tuning loop with memory:
1. Loads accumulated learnings from previous iterations
2. Runs the current drafting prompt against sample profiles/jobs
3. Uses LLM-as-a-judge to score outputs on 6 dimensions
4. LEARNS from grader feedback and updates memory
5. Provides targeted suggestions based on patterns in memory

Memory-guided tuning:
- After each iteration, the loop analyzes what worked/didn't work
- Learnings are stored in drafting_memory.json
- Use --show-memory to see patterns that should guide prompt changes
- Memory persists across sessions for continuous improvement

After each iteration:
1. Review the learned insights printed after grading
2. Use --show-memory to see accumulated patterns
3. Modify workflow/nodes/drafting.py based on memory guidance
4. Run --iterate again to measure improvement
"""

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from evals.drafting_tuning_loop import DraftingTuningLoop
from evals.graders.drafting_llm_grader import DraftingLLMGrader

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


def create_draft_generator(memory_context: str = ""):
    """Create a draft generator that mirrors the production pipeline.

    Uses the same _build_drafting_context_from_raw function and message format
    as the production draft_resume_node, so tuning scores reflect real behavior.

    Args:
        memory_context: Accumulated learnings to guide drafting style.

    Returns:
        Async function that generates drafts matching production pipeline.
    """

    async def generate_draft(profile: dict, job: dict, profile_text: str = "") -> str:
        """Generate a resume draft using the production code path.

        Mirrors draft_resume_node in workflow/nodes/drafting.py:
        1. Builds context via _build_drafting_context_from_raw
        2. Uses RESUME_DRAFTING_PROMPT as system message
        3. Sends "Create an ATS-optimized resume based on:" as user message
        4. Extracts HTML from code blocks if needed
        """
        from langchain_anthropic import ChatAnthropic
        from langchain_core.messages import HumanMessage, SystemMessage
        from config import get_settings
        from workflow.nodes.drafting import (
            RESUME_DRAFTING_PROMPT,
            _build_drafting_context_from_raw,
            _extract_content_from_code_block,
        )

        settings = get_settings()
        llm = ChatAnthropic(
            model=settings.anthropic_model,
            api_key=settings.anthropic_api_key,
            temperature=0.3,
            max_tokens=4096,
        )

        # Build context using the same function as production
        context = _build_drafting_context_from_raw(
            profile_text=profile_text,
            job_text=job.get("description", ""),
            profile_name=profile.get("name", "Candidate"),
            job_title=job.get("title", "Position"),
            job_company=job.get("company_name", "Company"),
            user_profile=profile,
            job_posting=job,
            gap_analysis={},
            qa_history=[],
            research={},
            discovered_experiences=[],
            user_preferences=None,
        )

        # Build system prompt with memory context if available
        system_prompt = RESUME_DRAFTING_PROMPT
        if memory_context:
            system_prompt += f"\n\n---\n\n{memory_context}"

        # Same message format as production (drafting.py line 275)
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Create an ATS-optimized resume based on:\n\n{context}"),
        ]

        response = await llm.ainvoke(messages)

        # Extract HTML from code blocks, same as production (drafting.py line 280)
        return _extract_content_from_code_block(response.content, "html")

    return generate_draft


async def run_iteration():
    """Run one iteration of the tuning loop with memory."""
    grader = DraftingLLMGrader()
    loop = DraftingTuningLoop(grader)

    # Get memory context for this iteration
    memory_context = loop.get_memory_context()
    if loop.memory.get("iteration_count", 0) > 0:
        logger.info(f"Loaded {loop.memory['iteration_count']} iterations of learnings from memory")

    logger.info("Running drafting tuning iteration...")

    # Create draft generator with memory context
    draft_generator = create_draft_generator(memory_context)
    result = await loop.run_iteration(draft_generator)

    print("\n" + "="*60)
    print("DRAFTING TUNING ITERATION RESULT")
    print("="*60)
    print(f"Current Score: {result['current_score']:.1f}/100")
    print(f"Baseline Score: {result['baseline_score']:.1f}/100")
    print(f"Improvement: {result['improvement_percent']}")
    print(f"Target Met: {'YES ✓' if result['target_met'] else 'NO'}")
    print(f"Iterations: {result['iterations']}")

    if "dimension_breakdown" in result:
        print("\nDimension Breakdown:")
        for dim, score in result["dimension_breakdown"].items():
            indicator = " ← WEAKEST" if score == min(result["dimension_breakdown"].values()) else ""
            print(f"  {dim}: {score:.1f}{indicator}")

    # Show what was learned this iteration
    if learned := result.get("learned"):
        print("\n" + "-"*40)
        print("LEARNED THIS ITERATION:")
        print("-"*40)

        if learned.get("new_insights"):
            print("\nNew Insights:")
            for insight in learned["new_insights"]:
                print(f"  • {insight}")

        if learned.get("next_focus"):
            focus = learned["next_focus"]
            print(f"\nNext Focus Area: {focus['dimension']} (score: {focus['score']:.1f})")
            if focus.get("suggested_improvements"):
                print("  Suggested improvements:")
                for imp in focus["suggested_improvements"][:3]:
                    print(f"    - {imp}")

    print("\n" + "-"*40)
    print("TOP SUGGESTIONS FOR PROMPT TUNING:")
    print("-"*40)
    for i, suggestion in enumerate(result["suggestions"][:5], 1):
        print(f"  {i}. {suggestion}")

    print("\nDetailed Results:")
    for r in result["detailed_results"]:
        grade = r["grade"]
        print(f"  - {r['sample_id']}: {grade['overall_score']:.0f}/100")
        if reasoning := grade.get("reasoning"):
            print(f"    Reasoning: {reasoning[:100]}...")

    print("\n" + "="*60)
    print("NEXT STEPS:")
    print("="*60)
    print("1. Run --show-memory to see all accumulated learnings")
    print("2. Modify workflow/nodes/drafting.py based on learnings")
    print("3. Run --iterate again to measure improvement")

    return result


def check_status():
    """Check current tuning loop status including memory."""
    loop = DraftingTuningLoop()
    status = loop.get_loop_status()

    print("\n" + "="*60)
    print("DRAFTING TUNING LOOP STATUS")
    print("="*60)
    print(f"Status: {status['status']}")
    print(f"Message: {status['message']}")

    # Memory summary
    if loop.memory:
        print(f"\nMemory: {loop.memory.get('iteration_count', 0)} iterations of learnings")
        if loop.memory.get("current_best_score"):
            print(f"Best Score Ever: {loop.memory['current_best_score']:.1f}/100")

    if status["status"] == "IN_PROGRESS":
        print(f"\nCurrent Score: {status['current_score']:.1f}/100")
        print(f"Baseline Score: {status['baseline_score']:.1f}/100")
        print(f"Improvement: {status['improvement_percent']}")
        print(f"Remaining Gap: {status['remaining_gap']:.1%}")
        print(f"Weakest Dimension: {status['weakest_dimension']} ({status['weakest_score']:.0f})")

        if breakdown := status.get("dimension_breakdown"):
            print("\nDimension Breakdown:")
            for dim, score in breakdown.items():
                indicator = " ← FOCUS" if dim == status['weakest_dimension'] else ""
                print(f"  {dim}: {score:.1f}{indicator}")

        print("\nSuggestions from Last Iteration:")
        for i, s in enumerate(status.get("suggestions_for_next_iteration", [])[:3], 1):
            print(f"  {i}. {s}")

        # Show memory insights if available
        if loop.memory.get("learnings"):
            weakest = status['weakest_dimension']
            dim_learnings = loop.memory["learnings"].get(weakest, {})
            improvements = dim_learnings.get("specific_improvements", [])
            if improvements:
                print(f"\nMemory Insights for {weakest}:")
                for imp in improvements[-3:]:
                    print(f"  • {imp}")

    elif status["status"] == "TARGET_MET":
        print(f"\nFinal Score: {status['final_score']:.1f}/100")
        print(f"Iterations Taken: {status['iterations_taken']}")

    print("\nRun --show-memory to see full accumulated learnings")
    return status


def reset_loop():
    """Reset the tuning loop."""
    loop = DraftingTuningLoop()
    loop.reset()
    print("Tuning loop reset. Run --iterate to start fresh.")


def show_memory():
    """Display accumulated learnings from memory."""
    loop = DraftingTuningLoop()
    loop.show_memory()


def reset_memory():
    """Reset memory to start fresh learnings."""
    loop = DraftingTuningLoop()
    loop.reset_memory()
    print("Memory reset. Learnings cleared.")
    print("Note: History is preserved. Use --reset to also clear history.")


def run_validation():
    """Run programmatic validation checks only (no LLM calls).

    Validates sample resumes against the programmatic checks in validate_resume():
    - Summary word count (<= 50)
    - Bullet word count (<= 15)
    - Compound sentence detection
    - Quantification rate (>= 50%)
    - AI-tell word/phrase detection
    - Rhythm variation (no 3+ uniform consecutive bullets)
    - Summary years+domain grounded in source (scope conflation)
    - No ungrounded scale claims (company-to-individual attribution)
    - Keyword coverage (>= 30% of job posting key terms)
    - Reverse chronological order (newest experience first)
    - Action verb usage
    - Required sections (skills, education)
    """
    from workflow.nodes.drafting import validate_resume

    samples_path = Path(__file__).parent / "datasets" / "drafting_samples.json"
    with open(samples_path) as f:
        data = json.load(f)

    print("\n" + "=" * 60)
    print("PROGRAMMATIC VALIDATION (no LLM calls)")
    print("=" * 60)
    print(f"Samples: {len(data['samples'])}")
    print(f"Checks: summary_length, bullet_word_count, no_compound_bullets, quantification_rate, ai_tells_clean, rhythm_variation, summary_years_grounded, no_ungrounded_scale, keyword_coverage, reverse_chronological, action_verbs, skills_section, education_section")
    print()

    # This runs validation on any pre-existing drafts if available
    # For now, just confirm the validation function works
    test_html = """
    <h1>Test Candidate</h1>
    <p>test@email.com</p>
    <h2>Professional Summary</h2>
    <p>Backend engineer with 5 years building distributed systems at scale.</p>
    <h2>Experience</h2>
    <h3>Engineer | Company | 2020-Present</h3>
    <ul>
    <li>Built backend API serving 10K users</li>
    <li>Reduced latency 40% via caching</li>
    <li>Led team of 5 engineers</li>
    </ul>
    <h2>Skills</h2>
    <p>Python, JavaScript</p>
    <h2>Education</h2>
    <p><strong>BS CS</strong> - University, 2018</p>
    """

    result = validate_resume(test_html)
    print("Sample validation result:")
    for check, passed in result.checks.items():
        status = "PASS" if passed else "FAIL"
        print(f"  [{status}] {check}")
    if result.errors:
        print(f"\nErrors: {result.errors}")
    if result.warnings:
        print(f"Warnings: {result.warnings}")
    print(f"\nOverall valid: {result.valid}")


def main():
    parser = argparse.ArgumentParser(
        description="Drafting prompt tuning loop with memory",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m evals.run_drafting_tuning --iterate      # Run one iteration
  python -m evals.run_drafting_tuning --show-memory  # See what's been learned
  python -m evals.run_drafting_tuning --check        # Check progress

Memory-guided workflow:
  1. Run --iterate to generate drafts and learn from feedback
  2. Run --show-memory to see accumulated patterns
  3. Modify the drafting prompt based on learnings
  4. Repeat until target improvement is reached
"""
    )
    parser.add_argument("--check", action="store_true", help="Check current status")
    parser.add_argument("--iterate", action="store_true", help="Run one iteration")
    parser.add_argument("--reset", action="store_true", help="Reset history (keeps memory)")
    parser.add_argument("--show-memory", action="store_true", help="Show accumulated learnings")
    parser.add_argument("--reset-memory", action="store_true", help="Reset memory learnings")
    parser.add_argument("--show-prompt", action="store_true", help="Show current drafting prompt")
    parser.add_argument("--validate", action="store_true", help="Run programmatic validation only (no LLM calls)")

    args = parser.parse_args()

    if args.validate:
        run_validation()
    elif args.check:
        check_status()
    elif args.iterate:
        asyncio.run(run_iteration())
    elif args.reset:
        reset_loop()
    elif args.show_memory:
        show_memory()
    elif args.reset_memory:
        reset_memory()
    elif args.show_prompt:
        # Show the current drafting prompt for reference
        prompt_path = Path(__file__).parent.parent / "workflow" / "nodes" / "drafting.py"
        if prompt_path.exists():
            import re
            content = prompt_path.read_text()
            # Extract RESUME_DRAFTING_PROMPT
            match = re.search(r'RESUME_DRAFTING_PROMPT\s*=\s*"""(.+?)"""', content, re.DOTALL)
            if match:
                print("Current RESUME_DRAFTING_PROMPT:")
                print("-" * 40)
                print(match.group(1).strip())
            else:
                print("Could not find RESUME_DRAFTING_PROMPT in drafting.py")
        else:
            print(f"Prompt file not found: {prompt_path}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
