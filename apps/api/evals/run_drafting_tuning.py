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
3. Uses LLM-as-a-judge to score outputs on 4 dimensions
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
    """Create a draft generator function with optional memory context.

    Args:
        memory_context: Accumulated learnings to guide drafting style.

    Returns:
        Async function that generates drafts.
    """

    async def generate_draft(profile: dict, job: dict) -> str:
        """Generate a resume draft using the current drafting node.

        This calls the actual drafting logic to test the current prompt.
        """
        from langchain_anthropic import ChatAnthropic
        from config import get_settings
        from workflow.nodes.drafting import RESUME_DRAFTING_PROMPT

        settings = get_settings()
        llm = ChatAnthropic(
            model=settings.anthropic_model,
            api_key=settings.anthropic_api_key,
            temperature=0.3,
        )

        # Build context similar to what the drafting node receives
        profile_summary = f"""
Name: {profile.get('name', 'Unknown')}
Headline: {profile.get('headline', '')}
Summary: {profile.get('summary', '')}

Experience:
"""
        for exp in profile.get('experience', []):
            profile_summary += f"\n- {exp.get('position', '')} at {exp.get('company', '')}"
            if desc := exp.get('description'):
                profile_summary += f"\n  {desc}"
            if achievements := exp.get('achievements'):
                for ach in achievements:
                    profile_summary += f"\n  * {ach}"

        profile_summary += f"\n\nSkills: {', '.join(profile.get('skills', []))}"

        if edu := profile.get('education'):
            profile_summary += "\n\nEducation:"
            for e in edu:
                profile_summary += f"\n- {e.get('degree', '')} from {e.get('institution', '')}"

        if certs := profile.get('certifications'):
            profile_summary += f"\n\nCertifications: {', '.join(certs)}"

        job_summary = f"""
Title: {job.get('title', '')}
Company: {job.get('company_name', '')}
Description: {job.get('description', '')}

Requirements: {', '.join(job.get('requirements', []))}
Tech Stack: {', '.join(job.get('tech_stack', []))}
Responsibilities: {', '.join(job.get('responsibilities', []))}
"""

        from langchain_core.messages import HumanMessage, SystemMessage

        # Build system prompt with memory context if available
        system_prompt = RESUME_DRAFTING_PROMPT
        if memory_context:
            system_prompt += f"\n\n---\n\n{memory_context}"

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"""Create an ATS-optimized resume for this candidate targeting the specified job.

## Candidate Profile
{profile_summary}

## Target Job
{job_summary}

Generate the resume in clean HTML format suitable for export to DOCX/PDF.
Focus on highlighting relevant experience and achievements that match the job requirements.
Include quantified achievements where available."""),
        ]

        response = await llm.ainvoke(messages)
        return response.content

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

    args = parser.parse_args()

    if args.check:
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
