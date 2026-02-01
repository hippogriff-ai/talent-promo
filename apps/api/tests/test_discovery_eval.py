"""Tests for discovery prompt evaluation harness.

Tests verify the eval dataset structure, grader functionality,
and tuning loop mechanics.
"""

import json
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock


class TestDiscoveryDataset:
    """Tests for the discovery evaluation dataset."""

    def test_dataset_file_exists(self):
        """Dataset file should exist at expected path."""
        dataset_path = Path(__file__).parent.parent / "evals" / "datasets" / "discovery_samples.json"
        assert dataset_path.exists(), f"Dataset not found at {dataset_path}"

    def test_dataset_has_required_structure(self):
        """Dataset should have required fields."""
        dataset_path = Path(__file__).parent.parent / "evals" / "datasets" / "discovery_samples.json"
        with open(dataset_path) as f:
            data = json.load(f)

        # Check top-level structure
        assert "samples" in data
        assert "version" in data
        assert len(data["samples"]) >= 3, "Need at least 3 samples"

    def test_samples_have_required_fields(self):
        """Each sample should have required fields."""
        dataset_path = Path(__file__).parent.parent / "evals" / "datasets" / "discovery_samples.json"
        with open(dataset_path) as f:
            data = json.load(f)

        required_fields = [
            "id",
            "description",
            "input",
            "expected_question_qualities",
            "gold_question_examples",
            "anti_patterns"
        ]

        for sample in data["samples"]:
            for field in required_fields:
                assert field in sample, f"Sample {sample.get('id', 'unknown')} missing field: {field}"

    def test_sample_input_has_required_fields(self):
        """Sample input should have user_profile, job_posting, gap_analysis."""
        dataset_path = Path(__file__).parent.parent / "evals" / "datasets" / "discovery_samples.json"
        with open(dataset_path) as f:
            data = json.load(f)

        for sample in data["samples"]:
            input_data = sample["input"]
            assert "user_profile" in input_data
            assert "job_posting" in input_data
            assert "gap_analysis" in input_data

    def test_gold_examples_not_empty(self):
        """Each sample should have at least one gold example question."""
        dataset_path = Path(__file__).parent.parent / "evals" / "datasets" / "discovery_samples.json"
        with open(dataset_path) as f:
            data = json.load(f)

        for sample in data["samples"]:
            assert len(sample["gold_question_examples"]) >= 1, \
                f"Sample {sample['id']} has no gold examples"

    def test_anti_patterns_not_empty(self):
        """Each sample should have at least one anti-pattern."""
        dataset_path = Path(__file__).parent.parent / "evals" / "datasets" / "discovery_samples.json"
        with open(dataset_path) as f:
            data = json.load(f)

        for sample in data["samples"]:
            assert len(sample["anti_patterns"]) >= 1, \
                f"Sample {sample['id']} has no anti-patterns"


class TestDiscoveryGrader:
    """Tests for the LLM-as-a-judge grader."""

    def test_grader_imports(self):
        """Grader module should import without errors."""
        from evals.graders.discovery_grader import DiscoveryGrader, GRADING_PROMPT
        assert DiscoveryGrader is not None
        assert GRADING_PROMPT is not None

    def test_grader_prompt_has_dimensions(self):
        """Grading prompt should include all 5 dimensions."""
        from evals.graders.discovery_grader import GRADING_PROMPT

        dimensions = [
            "Strength-to-Gap Bridge",
            "Conversational Agility",
            "Executive Coach Voice",
            "Hidden Value Finder",
            "Specificity"
        ]

        for dim in dimensions:
            assert dim in GRADING_PROMPT, f"Missing dimension: {dim}"

    def test_grader_prompt_has_anti_patterns(self):
        """Grading prompt should mention anti-patterns."""
        from evals.graders.discovery_grader import GRADING_PROMPT

        assert "anti-pattern" in GRADING_PROMPT.lower() or "Anti-pattern" in GRADING_PROMPT

    @pytest.mark.asyncio
    async def test_grader_grade_method(self):
        """Grader.grade should return structured result."""
        from evals.graders.discovery_grader import DiscoveryGrader

        # Mock the Anthropic client
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=json.dumps({
            "overall_score": 75,
            "dimension_scores": {
                "thought_provoking": 70,
                "specificity_seeker": 80,
                "gap_relevance": 75,
                "hidden_value_finder": 75
            },
            "reasoning": "Test reasoning",
            "best_question": "Best question text",
            "worst_question": "Worst question text",
            "suggestions": ["Suggestion 1", "Suggestion 2"]
        }))]
        mock_client.messages.create.return_value = mock_response

        grader = DiscoveryGrader(client=mock_client)

        sample = {
            "input": {
                "user_profile": {"name": "Test User"},
                "job_posting": {"title": "Test Role"},
                "gap_analysis": {"gaps": ["Gap 1"]}
            },
            "gold_question_examples": ["Gold question?"],
            "anti_patterns": ["Bad question?"]
        }

        result = await grader.grade(sample, ["Question 1?", "Question 2?"])

        assert "overall_score" in result
        assert "dimension_scores" in result
        assert "suggestions" in result
        assert result["overall_score"] == 75


class TestDiscoveryTuningLoop:
    """Tests for the tuning loop runner."""

    def test_tuning_loop_imports(self):
        """Tuning loop module should import without errors."""
        from evals.discovery_tuning_loop import DiscoveryTuningLoop
        assert DiscoveryTuningLoop is not None

    def test_loop_initial_status(self):
        """New loop should have NOT_STARTED status."""
        from evals.discovery_tuning_loop import DiscoveryTuningLoop
        from evals.graders.discovery_grader import DiscoveryGrader

        mock_client = MagicMock()
        grader = DiscoveryGrader(client=mock_client)
        loop = DiscoveryTuningLoop(grader)

        status = loop.get_loop_status()
        assert status["status"] == "NOT_STARTED"

    def test_loop_loads_samples(self):
        """Loop should be able to load samples from dataset."""
        from evals.discovery_tuning_loop import DiscoveryTuningLoop
        from evals.graders.discovery_grader import DiscoveryGrader

        mock_client = MagicMock()
        grader = DiscoveryGrader(client=mock_client)
        loop = DiscoveryTuningLoop(grader)

        samples = loop._load_samples()
        assert len(samples) >= 3

    def test_loop_constants(self):
        """Loop should have sensible target and max iterations."""
        from evals.discovery_tuning_loop import TARGET_IMPROVEMENT, MAX_ITERATIONS

        assert TARGET_IMPROVEMENT == 0.15, "Target should be 15%"
        assert MAX_ITERATIONS == 10, "Max iterations should be 10"


class TestRunDiscoveryTuning:
    """Tests for the CLI runner."""

    def test_cli_module_imports(self):
        """CLI module should import without errors."""
        # This just tests the module can be imported
        import evals.run_discovery_tuning
        assert evals.run_discovery_tuning is not None
