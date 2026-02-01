"""CLI for Discovery Prompt Tuning Loop.

This script allows coding agents to iteratively improve discovery prompts
by running evaluations and getting feedback.

Usage:
    python -m evals.run_discovery_tuning --check      # Check current score (baseline)
    python -m evals.run_discovery_tuning --iterate    # Run one iteration
    python -m evals.run_discovery_tuning --status     # Show loop status
    python -m evals.run_discovery_tuning --history    # Show iteration history
    python -m evals.run_discovery_tuning --save       # Save history to file

Environment:
    ANTHROPIC_API_KEY must be set for LLM grading.

Example workflow for coding agent:
    1. Run --check to establish baseline score
    2. Review suggestions and modify discovery.py prompts
    3. Run --iterate to test improvements
    4. Repeat steps 2-3 until --status shows TARGET_MET
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load config to get API key from .env
from config import get_settings
settings = get_settings()

# Set env var from config if not already set
if settings.anthropic_api_key and not os.getenv("ANTHROPIC_API_KEY"):
    os.environ["ANTHROPIC_API_KEY"] = settings.anthropic_api_key

from evals.graders.discovery_grader import DiscoveryGrader
from evals.discovery_tuning_loop import DiscoveryTuningLoop

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


# State file to persist loop state between runs
STATE_FILE = Path(__file__).parent / ".discovery_tuning_state.json"


def load_state() -> dict:
    """Load persisted loop state."""
    if STATE_FILE.exists():
        with open(STATE_FILE) as f:
            return json.load(f)
    return {"baseline_score": None, "history": []}


def save_state(loop: DiscoveryTuningLoop) -> None:
    """Persist loop state to file."""
    state = {
        "baseline_score": loop.baseline_score,
        "history": loop.history
    }
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def restore_loop(grader: DiscoveryGrader) -> DiscoveryTuningLoop:
    """Restore loop from persisted state."""
    loop = DiscoveryTuningLoop(grader)
    state = load_state()
    loop.baseline_score = state.get("baseline_score")
    loop.history = state.get("history", [])
    return loop


async def create_question_generator():
    """Create a question generator that uses the actual discovery node.

    Returns:
        Async function that generates questions from sample input.
    """
    # Import the actual discovery question generator
    from workflow.nodes.discovery import generate_discovery_prompts

    async def generator(sample_input: dict) -> list[str]:
        """Generate discovery questions for a sample.

        Args:
            sample_input: Dict with user_profile, job_posting, gap_analysis.

        Returns:
            List of generated questions.
        """
        # Build context similar to what the discovery node receives
        profile = sample_input["user_profile"]
        job = sample_input["job_posting"]
        gaps = sample_input["gap_analysis"]

        # Create a mock state with the required fields
        mock_state = {
            "user_profile": {
                "name": profile.get("name", "Unknown"),
                "headline": profile.get("headline", ""),
                "experience": profile.get("experience", []),
                "skills": profile.get("skills", [])
            },
            "job_posting": {
                "title": job.get("title", ""),
                "company_name": job.get("company", ""),
                "requirements": job.get("requirements", [])
            },
            "gap_analysis": {
                "gaps": gaps.get("gaps", []),
                "strengths": gaps.get("strengths", []),
                "opportunities": []  # Convert strengths to opportunities format
            },
            "qa_history": [],
            "qa_round": 0
        }

        # Generate questions using the actual prompt function
        prompts = await generate_discovery_prompts(mock_state)

        # Extract just the question text from the prompts
        questions = []
        for p in prompts:
            if isinstance(p, dict):
                questions.append(p.get("question", str(p)))
            else:
                questions.append(str(p))

        return questions

    return generator


async def run_check(loop: DiscoveryTuningLoop) -> None:
    """Run baseline check and display score."""
    print("\n" + "=" * 60)
    print("DISCOVERY PROMPT EVALUATION - BASELINE CHECK")
    print("=" * 60)

    generator = await create_question_generator()
    result = await loop.run_iteration(generator)
    save_state(loop)

    print(f"\n📊 Baseline Score: {result['current_score']:.1f}/100")
    print(f"📈 Target Improvement: {loop.get_loop_status().get('target_percent', '15%')}")

    if result["suggestions"]:
        print("\n💡 Suggestions for improvement:")
        for i, suggestion in enumerate(result["suggestions"], 1):
            print(f"   {i}. {suggestion}")

    print("\n📋 Individual sample scores:")
    for item in result["detailed_results"]:
        score = item["grade"]["overall_score"]
        desc = item["description"][:50]
        print(f"   • {item['sample_id']}: {score:.0f}/100 - {desc}...")

    print("\n✅ Baseline established. Now modify discovery.py and run --iterate")


async def run_iterate(loop: DiscoveryTuningLoop) -> None:
    """Run one iteration of the tuning loop."""
    print("\n" + "=" * 60)
    print(f"DISCOVERY PROMPT EVALUATION - ITERATION {len(loop.history) + 1}")
    print("=" * 60)

    generator = await create_question_generator()
    result = await loop.run_iteration(generator)
    save_state(loop)

    print(f"\n📊 Current Score: {result['current_score']:.1f}/100")
    print(f"📈 Baseline: {result['baseline_score']:.1f}/100")
    print(f"📈 Improvement: {result['improvement_percent']}")

    if result["target_met"]:
        print("\n🎉 TARGET MET! 15% improvement achieved!")
    else:
        remaining = 0.15 - result["improvement"]
        print(f"📈 Remaining to target: {remaining:.1%}")

    if result["suggestions"]:
        print("\n💡 Suggestions for next iteration:")
        for i, suggestion in enumerate(result["suggestions"], 1):
            print(f"   {i}. {suggestion}")

    print("\n📋 Individual sample scores:")
    for item in result["detailed_results"]:
        score = item["grade"]["overall_score"]
        prev_scores = [h["individual_scores"] for h in loop.history[:-1]]
        # Find previous score for this sample
        prev_score = None
        if prev_scores:
            for hist_scores in prev_scores[-1:]:  # Last iteration
                for s in hist_scores:
                    if s["sample"] == item["sample_id"]:
                        prev_score = s["score"]
                        break
        delta = f" ({score - prev_score:+.0f})" if prev_score else ""
        print(f"   • {item['sample_id']}: {score:.0f}/100{delta}")


def show_status(loop: DiscoveryTuningLoop) -> None:
    """Display current loop status."""
    print("\n" + "=" * 60)
    print("DISCOVERY PROMPT TUNING - STATUS")
    print("=" * 60)

    status = loop.get_loop_status()

    if status["status"] == "NOT_STARTED":
        print("\n⚪ Status: NOT STARTED")
        print("   Run --check to establish baseline score")
    elif status["status"] == "TARGET_MET":
        print("\n🎉 Status: TARGET MET!")
        print(f"   Final Score: {status['final_score']:.1f}/100")
        print(f"   Baseline: {status['baseline_score']:.1f}/100")
        print(f"   Improvement: {status['improvement']:.1%}")
        print(f"   Iterations: {status['iterations_taken']}")
    elif status["status"] == "MAX_ITERATIONS":
        print("\n🟡 Status: MAX ITERATIONS REACHED")
        print(f"   Best Score: {status['best_score']:.1f}/100")
        print("   Consider adjusting prompts more significantly")
    else:
        print("\n🔄 Status: IN PROGRESS")
        print(f"   Current: {status['current_score']:.1f}/100")
        print(f"   Baseline: {status['baseline_score']:.1f}/100")
        print(f"   Improvement: {status['improvement_percent']}")
        print(f"   Target: {status['target_percent']}")
        print(f"   Gap: {status['remaining_gap']:.1%}")

        if status.get("suggestions_for_next_iteration"):
            print("\n💡 Suggestions:")
            for s in status["suggestions_for_next_iteration"]:
                print(f"   • {s}")


def show_history(loop: DiscoveryTuningLoop) -> None:
    """Display iteration history."""
    print("\n" + "=" * 60)
    print("DISCOVERY PROMPT TUNING - HISTORY")
    print("=" * 60)

    if not loop.history:
        print("\n   No iterations yet. Run --check to start.")
        return

    print(f"\n📊 Baseline Score: {loop.baseline_score:.1f}/100")
    print(f"📋 Total Iterations: {len(loop.history)}")

    print("\n📈 Score progression:")
    for h in loop.history:
        improvement = ""
        if loop.baseline_score and loop.baseline_score > 0:
            imp = (h["score"] - loop.baseline_score) / loop.baseline_score
            improvement = f" ({imp:+.1%})"
        print(f"   Iteration {h['iteration']}: {h['score']:.1f}/100{improvement}")


async def main():
    """Main entry point for CLI."""
    parser = argparse.ArgumentParser(
        description="Discovery Prompt Tuning Loop",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument("--check", action="store_true",
                        help="Run baseline check (first iteration)")
    parser.add_argument("--iterate", action="store_true",
                        help="Run one tuning iteration")
    parser.add_argument("--status", action="store_true",
                        help="Show current loop status")
    parser.add_argument("--history", action="store_true",
                        help="Show iteration history")
    parser.add_argument("--save", action="store_true",
                        help="Save history to JSON file")
    parser.add_argument("--reset", action="store_true",
                        help="Reset loop state (start fresh)")
    parser.add_argument("--offline", action="store_true",
                        help="Run in offline mode (mock grading)")

    args = parser.parse_args()

    # Check for API key
    if not args.offline and not args.status and not args.history:
        if not os.getenv("ANTHROPIC_API_KEY"):
            print("❌ Error: ANTHROPIC_API_KEY not set")
            print("   Set the environment variable or use --offline for testing")
            sys.exit(1)

    print("\n🔍 Discovery Prompt Tuning Loop")
    print("=" * 60)

    # Initialize grader and loop
    grader = DiscoveryGrader()
    loop = restore_loop(grader)

    if args.reset:
        if STATE_FILE.exists():
            STATE_FILE.unlink()
        print("✅ Loop state reset. Run --check to start fresh.")
        return

    if args.status:
        show_status(loop)
    elif args.history:
        show_history(loop)
    elif args.save:
        path = loop.save_history()
        print(f"✅ History saved to: {path}")
    elif args.check:
        await run_check(loop)
    elif args.iterate:
        if loop.baseline_score is None:
            print("⚠️  No baseline score. Running --check first...")
            await run_check(loop)
        else:
            await run_iterate(loop)
    else:
        parser.print_help()


if __name__ == "__main__":
    asyncio.run(main())
