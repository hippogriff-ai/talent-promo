"""Tests for the evaluation harness.

These tests verify that:
1. Grading logic correctly scores drafts
2. Preference adherence is properly detected
3. Content quality metrics work correctly
4. ATS compatibility checks function
"""

import pytest
from evals.graders.drafting_grader import DraftingGrader, DraftScore


class TestDraftingGrader:
    """Test DraftingGrader scoring logic."""

    @pytest.fixture
    def grader(self):
        """Create grader instance."""
        return DraftingGrader()

    def test_grader_returns_draft_score(self, grader):
        """Test: Grader returns DraftScore object."""
        result = grader.grade("<p>Test resume</p>")
        assert isinstance(result, DraftScore)
        assert 0 <= result.overall <= 1

    def test_grader_scores_action_verbs(self, grader):
        """Test: Grader rewards action verbs in content."""
        good_draft = """
        <ul>
            <li>Led team of 10 engineers</li>
            <li>Managed $5M budget</li>
            <li>Developed new architecture</li>
            <li>Implemented CI/CD pipeline</li>
            <li>Designed microservices</li>
            <li>Delivered 3 major releases</li>
        </ul>
        """
        weak_draft = "<p>Was responsible for things. Did work. Helped with projects.</p>"

        good_score = grader.grade(good_draft)
        weak_score = grader.grade(weak_draft)

        assert good_score.content_quality > weak_score.content_quality

    def test_grader_scores_quantification(self, grader):
        """Test: Grader rewards quantified achievements."""
        quantified = """
        <ul>
            <li>Increased revenue by 40%</li>
            <li>Managed team of 15 people</li>
            <li>Reduced costs by $2M</li>
        </ul>
        """
        vague = "<p>Improved performance. Led team. Reduced costs.</p>"

        quant_score = grader.grade(quantified)
        vague_score = grader.grade(vague)

        assert quant_score.content_quality > vague_score.content_quality

    def test_grader_checks_formal_tone(self, grader):
        """Test: Grader detects formal vs conversational tone."""
        formal = "<p>Spearheaded implementation of enterprise solutions. Orchestrated cross-functional initiatives.</p>"
        casual = "<p>Helped with some projects. Got things done. Worked on stuff.</p>"

        formal_prefs = {"tone": "formal"}

        formal_score = grader.grade(formal, formal_prefs)
        casual_score = grader.grade(casual, formal_prefs)

        assert formal_score.preference_adherence > casual_score.preference_adherence

    def test_grader_checks_first_person(self, grader):
        """Test: Grader detects first person usage."""
        first_person = "<p>I led the team. I implemented new features. I drove results.</p>"
        no_first_person = "<p>Led the team. Implemented new features. Drove results.</p>"

        # Prefer first person
        prefs_yes = {"first_person": True}
        score_yes = grader.grade(first_person, prefs_yes)
        score_no = grader.grade(no_first_person, prefs_yes)
        assert score_yes.preference_adherence > score_no.preference_adherence

        # Prefer no first person
        prefs_no = {"first_person": False}
        score_yes = grader.grade(first_person, prefs_no)
        score_no = grader.grade(no_first_person, prefs_no)
        assert score_no.preference_adherence > score_yes.preference_adherence

    def test_grader_checks_heavy_metrics_preference(self, grader):
        """Test: Grader checks quantification preference."""
        metrics_heavy = """
        <ul>
            <li>Grew revenue 150%</li>
            <li>Managed 20 people</li>
            <li>Saved $3M annually</li>
        </ul>
        """
        qualitative = "<p>Significant improvements across all metrics. Strong leadership demonstrated.</p>"

        prefs = {"quantification_preference": "heavy_metrics"}

        heavy_score = grader.grade(metrics_heavy, prefs)
        qual_score = grader.grade(qualitative, prefs)

        assert heavy_score.preference_adherence > qual_score.preference_adherence

    def test_grader_checks_keyword_coverage(self, grader):
        """Test: Grader checks for job keywords."""
        keywords = ["Python", "AWS", "microservices", "Docker"]

        has_keywords = "<p>Expert in Python and AWS. Built microservices with Docker.</p>"
        missing_keywords = "<p>Experienced developer with strong skills.</p>"

        score_has = grader.grade(has_keywords, job_keywords=keywords)
        score_missing = grader.grade(missing_keywords, job_keywords=keywords)

        assert score_has.ats_compatibility > score_missing.ats_compatibility

    def test_grader_penalizes_tables_images(self, grader):
        """Test: Grader penalizes ATS-unfriendly elements."""
        clean = "<p>Clean resume content with proper formatting.</p>"
        with_table = "<table><tr><td>Skills</td></tr></table>"
        with_image = "<img src='photo.jpg' />"

        clean_score = grader.grade(clean)
        table_score = grader.grade(with_table)
        image_score = grader.grade(with_image)

        assert clean_score.ats_compatibility > table_score.ats_compatibility
        assert clean_score.ats_compatibility > image_score.ats_compatibility

    def test_grader_provides_feedback(self, grader):
        """Test: Grader provides actionable feedback."""
        weak_draft = "<p>Did some work.</p>"
        prefs = {"tone": "formal", "quantification_preference": "heavy_metrics"}

        score = grader.grade(weak_draft, prefs)

        assert len(score.feedback) > 0
        assert any("action verb" in fb.lower() for fb in score.feedback)

    def test_grader_penalizes_too_short(self, grader):
        """Test: Grader penalizes very short resumes."""
        short = "<p>Short resume.</p>"
        adequate = "<p>" + " ".join(["word"] * 300) + "</p>"

        short_score = grader.grade(short)
        adequate_score = grader.grade(adequate)

        assert adequate_score.content_quality > short_score.content_quality
        assert any("too short" in fb.lower() for fb in short_score.feedback)

    def test_grader_handles_empty_preferences(self, grader):
        """Test: Grader works with no preferences."""
        result = grader.grade("<p>Test content</p>", preferences=None)
        assert isinstance(result, DraftScore)
        assert result.preference_adherence > 0

    def test_grader_handles_empty_keywords(self, grader):
        """Test: Grader works with no keywords."""
        result = grader.grade("<p>Test content</p>", job_keywords=None)
        assert isinstance(result, DraftScore)
        assert result.ats_compatibility > 0


class TestOfflineEval:
    """Test offline evaluation mode."""

    def test_offline_eval_runs(self):
        """Test: Offline eval completes without errors."""
        from evals.run_eval import run_offline_eval

        result = run_offline_eval()

        assert "scores" in result
        assert result["scores"]["overall"] > 0

    def test_offline_eval_returns_feedback(self):
        """Test: Offline eval provides feedback."""
        from evals.run_eval import run_offline_eval

        result = run_offline_eval()

        assert "feedback" in result
        assert isinstance(result["feedback"], list)
