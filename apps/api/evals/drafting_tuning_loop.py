"""Drafting Prompt Tuning Loop with Memory.

Iteratively improves resume drafting prompts using accumulated learnings.
The loop learns from grader feedback and stores patterns that work/fail.

Memory Pattern:
    - Loads learnings from drafting_memory.json at start
    - After each iteration, analyzes grader feedback to extract patterns
    - Saves new learnings back to memory
    - Memory is used to guide prompt modifications between iterations

Usage:
    from evals.drafting_tuning_loop import DraftingTuningLoop
    loop = DraftingTuningLoop(grader, prompt_file_path)
    result = await loop.run_iteration(draft_generator)
    status = loop.get_loop_status()

CLI:
    cd apps/api && python -m evals.run_drafting_tuning --check
    cd apps/api && python -m evals.run_drafting_tuning --iterate
    cd apps/api && python -m evals.run_drafting_tuning --status
    cd apps/api && python -m evals.run_drafting_tuning --show-memory
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Callable, Awaitable, Optional, Any

from .graders.drafting_llm_grader import DraftingLLMGrader

logger = logging.getLogger(__name__)

TARGET_IMPROVEMENT = 0.15  # 15% improvement required
MAX_ITERATIONS = 10

# Dimensions we track
DIMENSIONS = ["job_relevance", "achievement_quality", "professional_quality", "ats_optimization"]


class IterationResult(dict):
    """Result from a single tuning iteration."""
    pass


class LoopStatus(dict):
    """Current status of the tuning loop."""
    pass


class DraftingTuningLoop:
    """Manages the drafting prompt tuning loop with memory.

    Tracks baseline score, runs iterations, learns from feedback, and
    stores accumulated learnings for future iterations.

    Memory Pattern:
        The loop maintains a memory file that stores:
        - Patterns that work well (from high-scoring dimensions)
        - Patterns to avoid (from low-scoring dimensions)
        - Specific improvements that have been applied
        - Sample-specific learnings

        This memory is:
        1. Loaded at initialization
        2. Used to provide context for prompt tuning decisions
        3. Updated after each iteration based on grader feedback
        4. Saved automatically for persistence
    """

    def __init__(
        self,
        grader: Optional[DraftingLLMGrader] = None,
        prompt_file_path: str = "workflow/nodes/drafting.py"
    ):
        """Initialize the tuning loop.

        Args:
            grader: DraftingLLMGrader instance for evaluating drafts.
            prompt_file_path: Path to the drafting prompts file (for reference).
        """
        self.grader = grader or DraftingLLMGrader()
        self.prompt_file = Path(prompt_file_path)
        self.history: list[dict] = []
        self.baseline_score: Optional[float] = None
        self._history_file = Path(__file__).parent / "drafting_tuning_history.json"
        self._memory_file = Path(__file__).parent / "drafting_memory.json"
        self.memory: dict[str, Any] = {}

        # Auto-load history if exists
        if self._history_file.exists():
            self.load_history(str(self._history_file))

        # Auto-load memory if exists
        if self._memory_file.exists():
            self._load_memory()

    def _load_samples(self) -> list[dict]:
        """Load samples from the silver dataset."""
        samples_path = Path(__file__).parent / "datasets" / "drafting_samples.json"
        with open(samples_path) as f:
            data = json.load(f)
        return data["samples"]

    async def run_iteration(
        self,
        draft_generator: Callable[[dict, dict], Awaitable[str]]
    ) -> IterationResult:
        """Run one iteration of the tuning loop.

        Args:
            draft_generator: Async function that takes (profile, job) and returns draft HTML.

        Returns:
            IterationResult with current score, improvement, and suggestions.
        """
        samples = self._load_samples()
        logger.info(f"Running iteration {len(self.history) + 1} with {len(samples)} samples")

        # Grade current drafts
        result = await self.grader.grade_batch(samples, draft_generator)

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
                    "job_relevance": r["grade"].get("job_relevance", 0),
                    "achievement_quality": r["grade"].get("achievement_quality", 0),
                    "professional_quality": r["grade"].get("professional_quality", 0),
                    "ats_optimization": r["grade"].get("ats_optimization", 0),
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

        # Auto-save history
        self.save_history()

        iteration_result = IterationResult({
            "current_score": result["average_score"],
            "baseline_score": self.baseline_score,
            "improvement": improvement,
            "improvement_percent": f"{improvement:.1%}",
            "target_met": improvement >= TARGET_IMPROVEMENT,
            "iterations": len(self.history),
            "suggestions": result["improvement_suggestions"],
            "detailed_results": result["individual_results"],
            "dimension_breakdown": self._get_dimension_breakdown(iteration),
        })

        # Learn from this iteration and update memory
        learned = self.learn_from_iteration(iteration_result)
        iteration_result["learned"] = learned

        return iteration_result

    def _get_dimension_breakdown(self, iteration: dict) -> dict:
        """Get average scores by dimension for analysis."""
        scores = iteration["individual_scores"]
        if not scores:
            return {}

        dimensions = ["job_relevance", "achievement_quality", "professional_quality", "ats_optimization"]
        breakdown = {}
        for dim in dimensions:
            values = [s.get(dim, 0) for s in scores]
            breakdown[dim] = sum(values) / len(values) if values else 0

        return breakdown

    def get_loop_status(self) -> LoopStatus:
        """Get current loop status for coding agent.

        Returns:
            LoopStatus indicating current state and next actions.
        """
        if not self.history:
            return LoopStatus({
                "status": "NOT_STARTED",
                "message": "Run first iteration with --iterate to establish baseline"
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

        # Identify weakest dimension for targeted improvement
        breakdown = self._get_dimension_breakdown(latest)
        weakest_dim = min(breakdown.items(), key=lambda x: x[1]) if breakdown else (None, 0)

        return LoopStatus({
            "status": "IN_PROGRESS",
            "current_score": latest["score"],
            "baseline_score": self.baseline_score,
            "improvement_so_far": improvement,
            "improvement_percent": f"{improvement:.1%}",
            "target": TARGET_IMPROVEMENT,
            "target_percent": f"{TARGET_IMPROVEMENT:.0%}",
            "remaining_gap": TARGET_IMPROVEMENT - improvement,
            "dimension_breakdown": breakdown,
            "weakest_dimension": weakest_dim[0],
            "weakest_score": weakest_dim[1],
            "suggestions_for_next_iteration": latest["suggestions"],
            "message": f"Score: {latest['score']:.1f}/100 | Improvement: {improvement:.1%} | Target: {TARGET_IMPROVEMENT:.0%} | Weakest: {weakest_dim[0]} ({weakest_dim[1]:.0f})"
        })

    def get_history(self) -> list[dict]:
        """Get full iteration history."""
        return self.history

    def save_history(self, path: Optional[str] = None) -> str:
        """Save tuning history for analysis.

        Args:
            path: Optional custom path. Defaults to standard location.

        Returns:
            Path where history was saved.
        """
        if path is None:
            path = str(self._history_file)

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

    def reset(self) -> None:
        """Reset the tuning loop to start fresh."""
        self.history = []
        self.baseline_score = None
        if self._history_file.exists():
            self._history_file.unlink()
        logger.info("Tuning loop reset")

    # ==========================================================================
    # MEMORY MANAGEMENT
    # ==========================================================================

    def _load_memory(self) -> None:
        """Load accumulated learnings from memory file."""
        try:
            with open(self._memory_file) as f:
                self.memory = json.load(f)
            logger.info(f"Loaded memory with {self.memory.get('iteration_count', 0)} iterations of learnings")
        except (json.JSONDecodeError, FileNotFoundError) as e:
            logger.warning(f"Could not load memory: {e}. Starting fresh.")
            self.memory = self._get_empty_memory()

    def _save_memory(self) -> None:
        """Save accumulated learnings to memory file."""
        self.memory["last_updated"] = datetime.now().isoformat()
        with open(self._memory_file, "w") as f:
            json.dump(self.memory, f, indent=2)
        logger.info(f"Memory saved with {len(self.memory.get('general_insights', []))} insights")

    def _get_empty_memory(self) -> dict[str, Any]:
        """Get empty memory structure."""
        return {
            "description": "Accumulated learnings from drafting prompt tuning iterations.",
            "last_updated": None,
            "iteration_count": 0,
            "baseline_score": None,
            "current_best_score": None,
            "learnings": {
                dim: {
                    "patterns_that_work": [],
                    "patterns_to_avoid": [],
                    "specific_improvements": []
                } for dim in DIMENSIONS
            },
            "general_insights": [],
            "sample_specific_learnings": {},
            "prompt_evolution": []
        }

    def learn_from_iteration(self, iteration_result: dict) -> dict[str, Any]:
        """Learn from the results of an iteration and update memory.

        This is the core learning function that:
        1. Analyzes dimension scores to identify strengths and weaknesses
        2. Extracts patterns from individual sample results
        3. Updates memory with new learnings
        4. Identifies what to focus on next

        Args:
            iteration_result: The result from run_iteration()

        Returns:
            Summary of what was learned
        """
        if not self.memory:
            self.memory = self._get_empty_memory()

        learned = {
            "new_insights": [],
            "dimension_learnings": {},
            "sample_learnings": [],
            "next_focus": None
        }

        # Update basic stats
        self.memory["iteration_count"] = len(self.history)
        if self.baseline_score:
            self.memory["baseline_score"] = self.baseline_score

        current_score = iteration_result.get("current_score", 0)
        if not self.memory.get("current_best_score") or current_score > self.memory["current_best_score"]:
            self.memory["current_best_score"] = current_score

        # Analyze dimension breakdown
        breakdown = iteration_result.get("dimension_breakdown", {})
        for dim in DIMENSIONS:
            score = breakdown.get(dim, 0)
            dim_learnings = self.memory["learnings"][dim]

            # High score (>= 80): capture what's working
            if score >= 80:
                insight = f"Iteration {len(self.history)}: Strong {dim} ({score:.0f}) - current approach effective"
                if insight not in dim_learnings["patterns_that_work"]:
                    dim_learnings["patterns_that_work"].append(insight)
                    learned["new_insights"].append(f"{dim}: approach is working well")

            # Low score (< 65): capture what to improve
            elif score < 65:
                suggestions = iteration_result.get("suggestions", [])
                relevant_suggestions = [s for s in suggestions if dim.replace("_", " ") in s.lower()]
                if relevant_suggestions:
                    for sug in relevant_suggestions[:2]:
                        if sug not in dim_learnings["specific_improvements"]:
                            dim_learnings["specific_improvements"].append(sug)
                            learned["new_insights"].append(f"{dim}: needs '{sug}'")

            learned["dimension_learnings"][dim] = {
                "score": score,
                "trend": self._get_dimension_trend(dim)
            }

        # Learn from individual samples
        detailed_results = iteration_result.get("detailed_results", [])
        for result in detailed_results:
            sample_id = result.get("sample_id", "unknown")
            grade = result.get("grade", {})

            # Store sample-specific learnings
            if sample_id not in self.memory["sample_specific_learnings"]:
                self.memory["sample_specific_learnings"][sample_id] = []

            sample_entry = {
                "iteration": len(self.history),
                "score": grade.get("overall_score", 0),
                "reasoning": grade.get("reasoning", ""),
                "improvements": result.get("improvements", [])
            }

            self.memory["sample_specific_learnings"][sample_id].append(sample_entry)
            learned["sample_learnings"].append({
                "sample_id": sample_id,
                "score": grade.get("overall_score", 0)
            })

        # Determine next focus area (weakest dimension)
        if breakdown:
            weakest = min(breakdown.items(), key=lambda x: x[1])
            learned["next_focus"] = {
                "dimension": weakest[0],
                "score": weakest[1],
                "suggested_improvements": self.memory["learnings"][weakest[0]]["specific_improvements"][-3:]
            }

        # Add general insight about this iteration
        improvement = iteration_result.get("improvement", 0)
        general_insight = {
            "iteration": len(self.history),
            "score": current_score,
            "improvement": f"{improvement:.1%}",
            "focus_was": learned["next_focus"]["dimension"] if learned["next_focus"] else "general",
            "timestamp": datetime.now().isoformat()
        }
        self.memory["general_insights"].append(general_insight)

        # Track prompt evolution (what was tried)
        self.memory["prompt_evolution"].append({
            "iteration": len(self.history),
            "score": current_score,
            "key_changes": iteration_result.get("suggestions", [])[:3],
            "timestamp": datetime.now().isoformat()
        })

        # Save updated memory
        self._save_memory()

        logger.info(f"Learned {len(learned['new_insights'])} new insights from iteration")
        return learned

    def _get_dimension_trend(self, dimension: str) -> str:
        """Get trend for a dimension across recent iterations."""
        if len(self.history) < 2:
            return "insufficient_data"

        recent_scores = []
        for h in self.history[-3:]:
            for s in h.get("individual_scores", []):
                if s.get(dimension):
                    recent_scores.append(s[dimension])

        if len(recent_scores) < 2:
            return "insufficient_data"

        avg_early = sum(recent_scores[:len(recent_scores)//2]) / (len(recent_scores)//2)
        avg_late = sum(recent_scores[len(recent_scores)//2:]) / (len(recent_scores) - len(recent_scores)//2)

        if avg_late > avg_early + 5:
            return "improving"
        elif avg_late < avg_early - 5:
            return "declining"
        return "stable"

    def get_memory_context(self) -> str:
        """Get memory context formatted for inclusion in prompts/guidance.

        Returns a human-readable summary of accumulated learnings that can be
        used to guide prompt modifications.
        """
        if not self.memory or not self.memory.get("learnings"):
            return "No learnings accumulated yet. This is the first iteration."

        lines = ["## Accumulated Learnings from Previous Iterations\n"]

        # Summary stats
        lines.append(f"Iterations completed: {self.memory.get('iteration_count', 0)}")
        if self.memory.get("baseline_score"):
            lines.append(f"Baseline score: {self.memory['baseline_score']:.1f}")
        if self.memory.get("current_best_score"):
            lines.append(f"Best score achieved: {self.memory['current_best_score']:.1f}")
        lines.append("")

        # Dimension-specific learnings
        for dim in DIMENSIONS:
            dim_data = self.memory["learnings"].get(dim, {})
            lines.append(f"### {dim.replace('_', ' ').title()}")

            works = dim_data.get("patterns_that_work", [])
            if works:
                lines.append("**What works:**")
                for w in works[-3:]:  # Last 3
                    lines.append(f"  - {w}")

            avoid = dim_data.get("patterns_to_avoid", [])
            if avoid:
                lines.append("**What to avoid:**")
                for a in avoid[-3:]:
                    lines.append(f"  - {a}")

            improve = dim_data.get("specific_improvements", [])
            if improve:
                lines.append("**Suggested improvements:**")
                for i in improve[-3:]:
                    lines.append(f"  - {i}")

            lines.append("")

        # Recent insights
        insights = self.memory.get("general_insights", [])
        if insights:
            lines.append("### Recent Iteration Summary")
            for insight in insights[-3:]:
                lines.append(f"- Iteration {insight['iteration']}: Score {insight['score']:.1f}, Focus: {insight['focus_was']}")

        return "\n".join(lines)

    def reset_memory(self) -> None:
        """Reset memory to start fresh learnings."""
        self.memory = self._get_empty_memory()
        self._save_memory()
        logger.info("Memory reset")

    def show_memory(self) -> None:
        """Print current memory state for debugging."""
        print("\n" + "="*60)
        print("DRAFTING TUNING MEMORY")
        print("="*60)
        print(self.get_memory_context())

        # Show sample-specific patterns
        sample_learnings = self.memory.get("sample_specific_learnings", {})
        if sample_learnings:
            print("\n### Sample-Specific Patterns")
            for sample_id, entries in sample_learnings.items():
                if entries:
                    latest = entries[-1]
                    print(f"  {sample_id}: Last score {latest['score']:.0f}")
                    if latest.get("improvements"):
                        print(f"    Needs: {', '.join(latest['improvements'][:2])}")
