"""Tests for dev harness prompt tuning framework."""

import pytest
import json
from pathlib import Path

from dev_harness.samples import load_sample, list_samples, SAMPLES_DIR
from dev_harness.comparators import StructuredComparator, LLMJudgeComparator
from dev_harness.runners import run_prompt_benchmark, PROMPTS


class TestSamples:
    """Test sample loading."""

    def test_list_profile_samples(self):
        """Can list profile samples."""
        samples = list_samples("profile")
        assert len(samples) > 0
        assert "001_faang_engineer" in samples

    def test_list_job_samples(self):
        """Can list job samples."""
        samples = list_samples("job")
        assert len(samples) > 0
        assert "001_senior_backend" in samples

    def test_load_profile_sample(self):
        """Can load a profile sample."""
        sample = load_sample("profile", "001_faang_engineer")
        assert "input" in sample
        assert "expected" in sample
        assert "metadata" in sample

        # Check expected structure
        expected = sample["expected"]
        assert expected["name"] == "John Smith"
        assert len(expected["experience"]) == 3
        assert len(expected["skills"]) == 10

    def test_load_job_sample(self):
        """Can load a job sample."""
        sample = load_sample("job", "001_senior_backend")
        assert "input" in sample
        assert "expected" in sample

        expected = sample["expected"]
        assert expected["title"] == "Senior Software Engineer - Backend"
        assert expected["company_name"] == "Acme Payments"
        assert len(expected["requirements"]) == 7

    def test_load_nonexistent_sample_raises(self):
        """Loading nonexistent sample raises error."""
        with pytest.raises(FileNotFoundError):
            load_sample("profile", "nonexistent")


class TestStructuredComparator:
    """Test programmatic comparison."""

    def test_exact_match(self):
        """Exact match gives 100% score."""
        comparator = StructuredComparator()
        data = {"name": "John", "skills": ["Python", "Go"]}

        report = comparator.compare(data, data)

        assert report.overall_score == 1.0
        assert len(report.missing_fields) == 0
        assert len(report.wrong_values) == 0

    def test_missing_field(self):
        """Missing field reduces score."""
        comparator = StructuredComparator()
        actual = {"name": "John"}
        expected = {"name": "John", "headline": "Engineer"}

        report = comparator.compare(actual, expected)

        assert report.overall_score < 1.0
        assert "headline" in report.missing_fields

    def test_list_comparison_partial(self):
        """Partial list match gets partial score."""
        comparator = StructuredComparator()
        actual = {"skills": ["Python", "Go"]}
        expected = {"skills": ["Python", "Go", "Java", "C++"]}

        report = comparator.compare(actual, expected)

        assert report.overall_score == 0.5  # 2/4 skills
        assert len(report.wrong_values) == 1

    def test_nested_dict_comparison(self):
        """Can compare nested dicts."""
        comparator = StructuredComparator()
        actual = {
            "experience": [
                {"company": "Google", "position": "SWE"}
            ]
        }
        expected = {
            "experience": [
                {"company": "Google", "position": "SWE"}
            ]
        }

        report = comparator.compare(actual, expected)
        assert report.overall_score == 1.0

    def test_extra_fields_detected(self):
        """Extra fields in actual are detected."""
        comparator = StructuredComparator()
        actual = {"name": "John", "extra_field": "value"}
        expected = {"name": "John"}

        report = comparator.compare(actual, expected)

        assert "extra_field" in report.extra_fields

    def test_fuzzy_string_match(self):
        """Fuzzy string matching works."""
        comparator = StructuredComparator(string_similarity_threshold=0.8)
        actual = {"name": "John Smith"}
        expected = {"name": "John W. Smith"}  # Slightly different

        report = comparator.compare(actual, expected)

        # Should still get decent score due to fuzzy matching
        assert report.overall_score >= 0.7

    def test_real_profile_sample(self):
        """Compare against real profile sample."""
        comparator = StructuredComparator()
        sample = load_sample("profile", "001_faang_engineer")

        # Simulate LLM output with some missing fields
        actual = {
            "name": "John Smith",
            "headline": "Senior Software Engineer at Google",
            "summary": sample["expected"]["summary"],
            "location": "San Francisco Bay Area",
            "experience": sample["expected"]["experience"][:2],  # Only 2 of 3
            "education": sample["expected"]["education"],
            "skills": sample["expected"]["skills"][:5],  # Only 5 of 10
            "certifications": []
        }

        report = comparator.compare(actual, sample["expected"])

        # Should pass some, fail some
        assert report.overall_score < 1.0
        assert report.overall_score > 0.5  # But still reasonable
        assert len(report.missing_fields) == 0  # No completely missing top-level fields

        print("\n" + report.summary())


class TestLLMJudgeComparator:
    """Test LLM-as-judge comparison (offline mode)."""

    def test_offline_judge(self):
        """Offline judging works without LLM."""
        judge = LLMJudgeComparator()

        actual = {"name": "John", "skills": ["Python"]}
        expected = {"name": "John", "skills": ["Python", "Go"]}

        verdict = judge.judge_offline("profile_extraction", actual, expected)

        assert verdict.overall_score < 1.0
        assert "completeness" in verdict.dimension_scores


class TestBenchmarkRunner:
    """Test benchmark running."""

    def test_offline_benchmark(self):
        """Can run benchmark in offline mode."""
        summary = run_prompt_benchmark(
            agent_type="profile",
            prompt_version="v1_original",
            offline=True,
        )

        assert summary.total_samples > 0
        assert summary.avg_score == 1.0  # Offline uses expected as actual
        assert summary.pass_count == summary.total_samples

    def test_prompts_defined(self):
        """Prompts are defined for profile and job extraction."""
        assert "profile_extraction" in PROMPTS
        assert "job_extraction" in PROMPTS

        assert "v1_original" in PROMPTS["profile_extraction"]
        assert "v1_original" in PROMPTS["job_extraction"]

    def test_prompt_has_required_keys(self):
        """Each prompt has system and user_template."""
        for agent_type, versions in PROMPTS.items():
            for version, config in versions.items():
                assert "system" in config, f"{agent_type}/{version} missing 'system'"
                assert "user_template" in config, f"{agent_type}/{version} missing 'user_template'"


class TestComparisonReport:
    """Test comparison report formatting."""

    def test_summary_output(self):
        """Summary is human-readable."""
        comparator = StructuredComparator()
        actual = {"name": "John"}
        expected = {"name": "John", "skills": ["Python"], "headline": "Engineer"}

        report = comparator.compare(actual, expected)
        summary = report.summary()

        assert "Overall Score:" in summary
        assert "MISSING" in summary
        assert "skills" in summary or "headline" in summary

    def test_to_dict(self):
        """Can convert to dict for JSON."""
        comparator = StructuredComparator()
        actual = {"name": "John"}
        expected = {"name": "John", "skills": ["Python"]}

        report = comparator.compare(actual, expected)
        data = report.to_dict()

        assert "overall_score" in data
        assert "missing_fields" in data
        assert isinstance(data["overall_score"], float)
