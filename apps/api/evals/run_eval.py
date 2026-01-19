"""Evaluation runner for resume agent workflow.

Usage:
    python -m evals.run_eval --stage drafting
    python -m evals.run_eval --stage drafting --dataset custom.json
    python -m evals.run_eval --stage drafting --upload  # Upload to LangSmith

This provides a local feedback loop for prompt tuning:
1. Run evals locally to see scores
2. Modify prompts in workflow/nodes/
3. Re-run evals to see impact
4. Optionally upload to LangSmith for tracking
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

# Add parent dir to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from evals.graders.drafting_grader import DraftingGrader, DraftScore

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


class EvalRunner:
    """Runner for evaluating workflow stages."""

    def __init__(self, upload_to_langsmith: bool = False):
        """Initialize eval runner.

        Args:
            upload_to_langsmith: Whether to upload results to LangSmith
        """
        self.upload = upload_to_langsmith
        self.client = None

        if self.upload:
            self._init_langsmith()

    def _init_langsmith(self):
        """Initialize LangSmith client."""
        try:
            from workflow.config import configure_langsmith, get_langsmith_client
            configure_langsmith()
            self.client = get_langsmith_client()
            if self.client:
                logger.info("LangSmith client initialized")
            else:
                logger.warning("LangSmith client unavailable - results will not be uploaded")
                self.upload = False
        except Exception as e:
            logger.warning(f"Failed to initialize LangSmith: {e}")
            self.upload = False

    def run_drafting_eval(self, dataset_path: str | None = None) -> dict:
        """Run drafting stage evaluation.

        Args:
            dataset_path: Path to custom dataset JSON, or None for default

        Returns:
            Evaluation results dict
        """
        # Load dataset
        if dataset_path:
            data_path = Path(dataset_path)
        else:
            data_path = Path(__file__).parent / "datasets" / "drafting_examples.json"

        if not data_path.exists():
            logger.error(f"Dataset not found: {data_path}")
            return {"error": "Dataset not found"}

        with open(data_path) as f:
            examples = json.load(f)

        logger.info(f"Loaded {len(examples)} examples from {data_path.name}")

        grader = DraftingGrader()
        results = []

        for example in examples:
            example_id = example["id"]
            logger.info(f"\n{'='*60}")
            logger.info(f"Evaluating: {example_id}")
            logger.info(f"Description: {example['description']}")

            # Generate draft using the workflow
            draft_html, run_id = self._generate_draft(example["input"])

            if not draft_html:
                logger.warning(f"  Failed to generate draft for {example_id}")
                results.append({
                    "id": example_id,
                    "error": "Draft generation failed",
                    "score": None
                })
                continue

            # Grade the draft
            score = grader.grade(
                draft_html=draft_html,
                preferences=example["input"].get("preferences"),
                job_keywords=example.get("expected_keywords", [])
            )

            # Log results
            logger.info(f"  Preference Adherence: {score.preference_adherence:.2f}")
            logger.info(f"  Content Quality: {score.content_quality:.2f}")
            logger.info(f"  ATS Compatibility: {score.ats_compatibility:.2f}")
            logger.info(f"  Overall Score: {score.overall:.2f}")
            if score.feedback:
                logger.info("  Feedback:")
                for fb in score.feedback:
                    logger.info(f"    - {fb}")

            result = {
                "id": example_id,
                "description": example["description"],
                "scores": {
                    "preference_adherence": score.preference_adherence,
                    "content_quality": score.content_quality,
                    "ats_compatibility": score.ats_compatibility,
                    "overall": score.overall
                },
                "feedback": score.feedback,
                "run_id": run_id
            }
            results.append(result)

            # Upload to LangSmith if enabled
            if self.upload and self.client and run_id:
                self._upload_feedback(run_id, score)

        # Calculate aggregate scores
        valid_results = [r for r in results if r.get("scores")]
        if valid_results:
            avg_scores = {
                "preference_adherence": sum(r["scores"]["preference_adherence"] for r in valid_results) / len(valid_results),
                "content_quality": sum(r["scores"]["content_quality"] for r in valid_results) / len(valid_results),
                "ats_compatibility": sum(r["scores"]["ats_compatibility"] for r in valid_results) / len(valid_results),
                "overall": sum(r["scores"]["overall"] for r in valid_results) / len(valid_results)
            }
        else:
            avg_scores = {}

        summary = {
            "stage": "drafting",
            "dataset": str(data_path),
            "timestamp": datetime.now().isoformat(),
            "total_examples": len(examples),
            "successful": len(valid_results),
            "average_scores": avg_scores,
            "results": results
        }

        # Print summary
        logger.info(f"\n{'='*60}")
        logger.info("EVALUATION SUMMARY")
        logger.info(f"{'='*60}")
        logger.info(f"Total examples: {len(examples)}")
        logger.info(f"Successful: {len(valid_results)}")
        if avg_scores:
            logger.info(f"\nAverage Scores:")
            logger.info(f"  Preference Adherence: {avg_scores['preference_adherence']:.2f}")
            logger.info(f"  Content Quality: {avg_scores['content_quality']:.2f}")
            logger.info(f"  ATS Compatibility: {avg_scores['ats_compatibility']:.2f}")
            logger.info(f"  Overall: {avg_scores['overall']:.2f}")

        return summary

    def _generate_draft(self, input_data: dict) -> tuple[str | None, str | None]:
        """Generate a resume draft using the workflow.

        Returns:
            Tuple of (draft_html, langsmith_run_id)
        """
        try:
            from workflow.nodes.drafting import draft_resume_node, _format_user_preferences
            from workflow.context import build_working_context

            # Build state for the draft node
            profile = input_data.get("profile", {})
            job = input_data.get("job_posting", {})
            preferences = input_data.get("preferences", {})

            state = {
                "user_profile": profile,
                "job_posting": job,
                "user_preferences": preferences,
                "gap_analysis": {
                    "gaps": [],
                    "strengths": [],
                    "opportunities": [],
                    "keywords_to_include": job.get("tech_stack", [])
                },
                "discovered_experiences": [],
                "resume_html": "",
                "current_step": "draft"
            }

            # Build context for prompt
            context = build_working_context(state)

            # Import the actual draft generation
            import asyncio
            result = asyncio.run(draft_resume_node(state))

            draft_html = result.get("resume_html", "")

            # Get run ID from LangSmith if available
            run_id = None
            if self.client:
                # LangSmith automatically tracks runs when tracing is enabled
                pass

            return draft_html, run_id

        except Exception as e:
            logger.error(f"Draft generation error: {e}")
            return None, None

    def _upload_feedback(self, run_id: str, score: DraftScore):
        """Upload evaluation feedback to LangSmith."""
        if not self.client or not run_id:
            return

        try:
            self.client.create_feedback(
                run_id=run_id,
                key="overall_score",
                score=score.overall,
                comment="; ".join(score.feedback) if score.feedback else "No issues"
            )
            logger.info(f"  Uploaded feedback to LangSmith (run: {run_id[:8]}...)")
        except Exception as e:
            logger.warning(f"  Failed to upload feedback: {e}")


def run_offline_eval(dataset_path: str | None = None) -> dict:
    """Run evaluation without LLM calls using mock data.

    This allows testing the grading logic without API costs.
    """
    grader = DraftingGrader()

    # Sample draft for testing grader
    sample_draft = """
    <h1>Alex Chen</h1>
    <h2>Senior Software Engineer</h2>
    <p>Experienced engineer with 5 years in full-stack development.</p>

    <h2>Experience</h2>
    <h3>TechCorp - Senior Software Engineer (2020-2024)</h3>
    <ul>
        <li>Led development of microservices architecture serving 10M users</li>
        <li>Implemented CI/CD pipeline reducing deployment time by 60%</li>
        <li>Managed team of 5 engineers delivering 3 major product launches</li>
        <li>Designed and built Python services handling 1M requests/day</li>
    </ul>

    <h2>Skills</h2>
    <p>Python, TypeScript, AWS, Docker, Kubernetes</p>
    """

    preferences = {
        "tone": "formal",
        "first_person": False,
        "quantification_preference": "heavy_metrics"
    }

    keywords = ["Python", "AWS", "microservices", "leadership"]

    score = grader.grade(sample_draft, preferences, keywords)

    logger.info("Offline Eval Results:")
    logger.info(f"  Preference Adherence: {score.preference_adherence:.2f}")
    logger.info(f"  Content Quality: {score.content_quality:.2f}")
    logger.info(f"  ATS Compatibility: {score.ats_compatibility:.2f}")
    logger.info(f"  Overall: {score.overall:.2f}")
    if score.feedback:
        logger.info("  Feedback:")
        for fb in score.feedback:
            logger.info(f"    - {fb}")

    return {
        "mode": "offline",
        "scores": {
            "preference_adherence": score.preference_adherence,
            "content_quality": score.content_quality,
            "ats_compatibility": score.ats_compatibility,
            "overall": score.overall
        },
        "feedback": score.feedback
    }


def main():
    """Main entry point for eval runner."""
    parser = argparse.ArgumentParser(description="Run workflow evaluations")
    parser.add_argument(
        "--stage",
        choices=["drafting"],
        default="drafting",
        help="Workflow stage to evaluate"
    )
    parser.add_argument(
        "--dataset",
        type=str,
        help="Path to custom dataset JSON file"
    )
    parser.add_argument(
        "--upload",
        action="store_true",
        help="Upload results to LangSmith"
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Run offline eval (no LLM calls, tests grading logic)"
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Path to save results JSON"
    )

    args = parser.parse_args()

    if args.offline:
        results = run_offline_eval(args.dataset)
    else:
        runner = EvalRunner(upload_to_langsmith=args.upload)

        if args.stage == "drafting":
            results = runner.run_drafting_eval(args.dataset)
        else:
            logger.error(f"Unknown stage: {args.stage}")
            sys.exit(1)

    # Save results if output path specified
    if args.output:
        output_path = Path(args.output)
        with open(output_path, "w") as f:
            json.dump(results, f, indent=2)
        logger.info(f"\nResults saved to: {output_path}")


if __name__ == "__main__":
    main()
