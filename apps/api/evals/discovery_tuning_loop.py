"""Discovery Prompt Tuning Loop.

Iteratively improves discovery prompts until achieving target improvement.
Designed for coding agents to run in a loop.

Usage:
    from evals.discovery_tuning_loop import DiscoveryTuningLoop
    loop = DiscoveryTuningLoop(grader, prompt_file_path)
    result = await loop.run_iteration(question_generator)
    status = loop.get_loop_status()
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Callable, Awaitable, Optional

from .graders.discovery_grader import DiscoveryGrader, BatchGradeResult

logger = logging.getLogger(__name__)

TARGET_IMPROVEMENT = 0.15  # 15% improvement required
MAX_ITERATIONS = 10


class IterationResult(dict):
    """Result from a single tuning iteration."""
    pass


class LoopStatus(dict):
    """Current status of the tuning loop."""
    pass


class DiscoveryTuningLoop:
    """Manages the discovery prompt tuning loop.

    Tracks baseline score, runs iterations, and determines when target is met.
    """

    def __init__(
        self,
        grader: DiscoveryGrader,
        prompt_file_path: str = "workflow/nodes/discovery.py"
    ):
        """Initialize the tuning loop.

        Args:
            grader: DiscoveryGrader instance for evaluating questions.
            prompt_file_path: Path to the discovery prompts file (for reference).
        """
        self.grader = grader
        self.prompt_file = Path(prompt_file_path)
        self.history: list[dict] = []
        self.baseline_score: Optional[float] = None

    def _load_samples(self) -> list[dict]:
        """Load samples from the silver dataset."""
        samples_path = Path(__file__).parent / "datasets" / "discovery_samples.json"
        with open(samples_path) as f:
            data = json.load(f)
        return data["samples"]

    async def run_iteration(
        self,
        question_generator: Callable[[dict], Awaitable[list[str]]]
    ) -> IterationResult:
        """Run one iteration of the tuning loop.

        Args:
            question_generator: Async function that takes sample input and returns questions.

        Returns:
            IterationResult with current score, improvement, and suggestions.
        """
        samples = self._load_samples()
        logger.info(f"Running iteration {len(self.history) + 1} with {len(samples)} samples")

        # Grade current prompt
        result = await self.grader.grade_batch(samples, question_generator)

        # Record history
        iteration = {
            "timestamp": datetime.now().isoformat(),
            "iteration": len(self.history) + 1,
            "score": result["average_score"],
            "suggestions": result["improvement_suggestions"],
            "individual_scores": [
                {
                    "sample": r["sample_id"],
                    "score": r["grade"]["overall_score"],
                    "reasoning": r["grade"].get("reasoning", "")
                }
                for r in result["individual_results"]
            ]
        }
        self.history.append(iteration)

        # Set baseline on first run
        if self.baseline_score is None:
            self.baseline_score = result["average_score"]
            logger.info(f"Baseline score set: {self.baseline_score:.1f}")

        # Calculate improvement
        if self.baseline_score > 0:
            improvement = (result["average_score"] - self.baseline_score) / self.baseline_score
        else:
            improvement = 0

        return IterationResult({
            "current_score": result["average_score"],
            "baseline_score": self.baseline_score,
            "improvement": improvement,
            "improvement_percent": f"{improvement:.1%}",
            "target_met": improvement >= TARGET_IMPROVEMENT,
            "iterations": len(self.history),
            "suggestions": result["improvement_suggestions"],
            "detailed_results": result["individual_results"]
        })

    def get_loop_status(self) -> LoopStatus:
        """Get current loop status for coding agent.

        Returns:
            LoopStatus indicating current state and next actions.
        """
        if not self.history:
            return LoopStatus({
                "status": "NOT_STARTED",
                "message": "Run first iteration with --iterate"
            })

        latest = self.history[-1]

        if self.baseline_score and self.baseline_score > 0:
            improvement = (latest["score"] - self.baseline_score) / self.baseline_score
        else:
            improvement = 0

        if improvement >= TARGET_IMPROVEMENT:
            return LoopStatus({
                "status": "TARGET_MET",
                "message": f"Achieved {improvement:.1%} improvement (target: {TARGET_IMPROVEMENT:.0%})",
                "final_score": latest["score"],
                "baseline_score": self.baseline_score,
                "improvement": improvement,
                "iterations_taken": len(self.history)
            })

        if len(self.history) >= MAX_ITERATIONS:
            return LoopStatus({
                "status": "MAX_ITERATIONS",
                "message": f"Reached {MAX_ITERATIONS} iterations. Best improvement: {improvement:.1%}",
                "best_score": max(h["score"] for h in self.history),
                "baseline_score": self.baseline_score
            })

        return LoopStatus({
            "status": "IN_PROGRESS",
            "current_score": latest["score"],
            "baseline_score": self.baseline_score,
            "improvement_so_far": improvement,
            "improvement_percent": f"{improvement:.1%}",
            "target": TARGET_IMPROVEMENT,
            "target_percent": f"{TARGET_IMPROVEMENT:.0%}",
            "remaining_gap": TARGET_IMPROVEMENT - improvement,
            "suggestions_for_next_iteration": latest["suggestions"],
            "message": f"Score: {latest['score']:.1f}/100 | Improvement: {improvement:.1%} | Target: {TARGET_IMPROVEMENT:.0%}"
        })

    def get_history(self) -> list[dict]:
        """Get full iteration history."""
        return self.history

    def save_history(self, path: Optional[str] = None) -> str:
        """Save tuning history for analysis.

        Args:
            path: Optional custom path. Defaults to timestamped filename.

        Returns:
            Path where history was saved.
        """
        if path is None:
            path = f"discovery_tuning_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        history_data = {
            "baseline_score": self.baseline_score,
            "final_score": self.history[-1]["score"] if self.history else None,
            "target_improvement": TARGET_IMPROVEMENT,
            "max_iterations": MAX_ITERATIONS,
            "iterations": self.history
        }

        with open(path, "w") as f:
            json.dump(history_data, f, indent=2)

        logger.info(f"History saved to {path}")
        return path

    def load_history(self, path: str) -> None:
        """Load previous tuning history to resume.

        Args:
            path: Path to history JSON file.
        """
        with open(path) as f:
            data = json.load(f)

        self.baseline_score = data.get("baseline_score")
        self.history = data.get("iterations", [])
        logger.info(f"Loaded history with {len(self.history)} iterations")
