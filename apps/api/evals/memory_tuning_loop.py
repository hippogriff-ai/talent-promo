"""Tuning loop for preference learning evaluation.

This module provides tools for:
1. Running evaluations on the preference learning prompt
2. Identifying weaknesses in preference inference
3. Iterating on the prompt to improve accuracy

Usage:
    # Single evaluation run
    python -m evals.memory_tuning_loop

    # Run iteration with target improvement
    python -m evals.memory_tuning_loop --iterate

    # Load specific prompt variant
    python -m evals.memory_tuning_loop --prompt-file path/to/prompt.txt
"""

import asyncio
import argparse
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from workflow.nodes.memory import learn_preferences_from_events
from evals.graders.memory_grader import grade_preference_learning, compute_aggregate_score

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Paths
EVALS_DIR = Path(__file__).parent
DATASETS_DIR = EVALS_DIR / "datasets"
RESULTS_DIR = EVALS_DIR / "results"

# Ensure results directory exists
RESULTS_DIR.mkdir(exist_ok=True)


def load_dataset() -> list[dict]:
    """Load the memory/preference learning evaluation dataset."""
    dataset_path = DATASETS_DIR / "memory_samples.json"
    with open(dataset_path) as f:
        return json.load(f)


async def evaluate_sample(sample: dict) -> dict[str, Any]:
    """Evaluate preference learning on a single sample.

    Args:
        sample: Sample with events and expected_preferences

    Returns:
        Evaluation result with grades and metadata
    """
    sample_id = sample.get("id", "unknown")
    events = sample.get("events", [])
    expected = sample.get("expected_preferences", {})

    logger.info(f"Evaluating sample: {sample_id}")

    try:
        # Run preference learning
        learned_result = await learn_preferences_from_events(events)

        # Grade the result
        grades = await grade_preference_learning(
            events=events,
            expected_preferences=expected,
            learned_result=learned_result,
        )

        # Check if expected preferences match
        correct_count = 0
        total_expected = len(expected)

        for key, expected_value in expected.items():
            learned_value = learned_result.get(key)
            if learned_value == expected_value:
                correct_count += 1

        return {
            "sample_id": sample_id,
            "description": sample.get("description", ""),
            "expected_preferences": expected,
            "learned_preferences": {
                k: learned_result.get(k)
                for k in ["tone", "structure", "sentence_length",
                          "first_person", "quantification_preference",
                          "achievement_focus"]
            },
            "confidence_scores": learned_result.get("confidence_scores", {}),
            "reasoning": learned_result.get("reasoning", ""),
            "grades": grades,
            "correct_count": correct_count,
            "total_expected": total_expected,
            "success": grades.get("overall_score", 0) >= 7,
        }

    except Exception as e:
        logger.error(f"Error evaluating sample {sample_id}: {e}")
        return {
            "sample_id": sample_id,
            "error": str(e),
            "grades": {
                "accuracy": 0,
                "confidence_calibration": 0,
                "reasoning_quality": 0,
                "overall_score": 0,
            },
            "success": False,
        }


async def run_evaluation() -> dict[str, Any]:
    """Run full evaluation on the dataset.

    Returns:
        Evaluation results with aggregate scores
    """
    dataset = load_dataset()
    logger.info(f"Loaded {len(dataset)} samples for evaluation")

    results = []
    for sample in dataset:
        result = await evaluate_sample(sample)
        results.append(result)

    # Compute aggregate scores
    grades = [r.get("grades", {}) for r in results]
    aggregate = compute_aggregate_score(grades)

    # Compute success rate
    successes = sum(1 for r in results if r.get("success", False))
    success_rate = successes / len(results) if results else 0

    return {
        "timestamp": datetime.now().isoformat(),
        "sample_count": len(dataset),
        "success_count": successes,
        "success_rate": success_rate,
        "aggregate_scores": aggregate,
        "individual_results": results,
    }


def save_results(results: dict, filename: str = None) -> str:
    """Save evaluation results to file.

    Args:
        results: Evaluation results dict
        filename: Optional custom filename

    Returns:
        Path to saved file
    """
    if filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"memory_eval_{timestamp}.json"

    filepath = RESULTS_DIR / filename
    with open(filepath, "w") as f:
        json.dump(results, f, indent=2)

    return str(filepath)


def print_results(results: dict):
    """Print evaluation results summary."""
    print("\n" + "=" * 60)
    print("PREFERENCE LEARNING EVALUATION RESULTS")
    print("=" * 60)

    print(f"\nSamples: {results['sample_count']}")
    print(f"Successes: {results['success_count']}")
    print(f"Success Rate: {results['success_rate']:.1%}")

    print("\nAggregate Scores (0-10):")
    agg = results["aggregate_scores"]
    print(f"  Accuracy:              {agg['accuracy']:.1f}")
    print(f"  Confidence Calibration: {agg['confidence_calibration']:.1f}")
    print(f"  Reasoning Quality:     {agg['reasoning_quality']:.1f}")
    print(f"  Overall:               {agg['overall_score']:.1f}")

    print("\nIndividual Results:")
    for result in results["individual_results"]:
        status = "PASS" if result.get("success") else "FAIL"
        sample_id = result.get("sample_id", "unknown")
        overall = result.get("grades", {}).get("overall_score", 0)
        print(f"  [{status}] {sample_id}: {overall:.1f}/10")

        if not result.get("success"):
            feedback = result.get("grades", {}).get("feedback", "")
            if feedback:
                print(f"        Feedback: {feedback[:100]}...")


async def run_iteration_loop(
    target_improvement: float = 0.15,
    max_iterations: int = 3,
) -> dict[str, Any]:
    """Run iterative improvement loop.

    Args:
        target_improvement: Target percentage improvement (0.15 = 15%)
        max_iterations: Maximum iterations to run

    Returns:
        Final evaluation results
    """
    logger.info(f"Starting iteration loop (target: {target_improvement:.0%} improvement)")

    # Run baseline evaluation
    baseline_results = await run_evaluation()
    baseline_score = baseline_results["aggregate_scores"]["overall_score"]

    print(f"\nBaseline Score: {baseline_score:.1f}/10")
    save_results(baseline_results, "memory_baseline.json")

    target_score = min(10, baseline_score * (1 + target_improvement))
    print(f"Target Score: {target_score:.1f}/10")

    current_results = baseline_results
    iteration = 0

    while iteration < max_iterations:
        iteration += 1
        current_score = current_results["aggregate_scores"]["overall_score"]

        if current_score >= target_score:
            print(f"\nTarget reached at iteration {iteration}!")
            break

        print(f"\n--- Iteration {iteration} ---")
        print(f"Current: {current_score:.1f}, Target: {target_score:.1f}")

        # Identify failing samples
        failing = [
            r for r in current_results["individual_results"]
            if not r.get("success")
        ]

        if not failing:
            print("All samples passing!")
            break

        print(f"Failing samples: {len(failing)}")
        for f in failing[:3]:
            print(f"  - {f.get('sample_id')}: {f.get('grades', {}).get('feedback', '')[:100]}")

        print("\nManual prompt tuning required.")
        print("Check: apps/api/workflow/nodes/memory.py (PREFERENCE_LEARNING_PROMPT)")
        print("After editing, re-run evaluation.")
        break

    return current_results


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Memory/Preference Learning Evaluation")
    parser.add_argument(
        "--iterate",
        action="store_true",
        help="Run iterative improvement loop",
    )
    parser.add_argument(
        "--target",
        type=float,
        default=0.15,
        help="Target improvement percentage (default: 0.15 = 15%%)",
    )
    args = parser.parse_args()

    if args.iterate:
        results = asyncio.run(run_iteration_loop(target_improvement=args.target))
    else:
        results = asyncio.run(run_evaluation())

    print_results(results)

    # Save results
    filepath = save_results(results)
    print(f"\nResults saved to: {filepath}")


if __name__ == "__main__":
    main()
