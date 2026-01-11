"""Tests for export stage functionality."""

import json
import pytest
from datetime import datetime

from workflow.state import ATSReport, LinkedInSuggestion, ExportOutput
from workflow.nodes.export import (
    optimize_for_ats,
    analyze_ats_compatibility,
    generate_linkedin_suggestions,
    html_to_text,
    html_to_json,
    html_to_docx,
    _extract_job_keywords,
    _generate_headline,
)


# ============================================================================
# Test Data
# ============================================================================


SAMPLE_RESUME_HTML = """
<h1>John Doe</h1>
<p>john.doe@email.com | (555) 123-4567 | San Francisco, CA</p>

<h2>Summary</h2>
<p>Experienced software engineer with 8+ years of expertise in Python, JavaScript, and cloud technologies. Led cross-functional teams to deliver scalable solutions that increased revenue by 25%.</p>

<h2>Experience</h2>

<h3>Senior Software Engineer</h3>
<p>Tech Company Inc. | 2020 - Present</p>
<ul>
    <li>Led development of microservices architecture serving 1M+ daily users</li>
    <li>Implemented CI/CD pipelines reducing deployment time by 60%</li>
    <li>Mentored team of 5 junior developers</li>
</ul>

<h3>Software Engineer</h3>
<p>Startup Corp | 2017 - 2020</p>
<ul>
    <li>Developed RESTful APIs using Python and FastAPI</li>
    <li>Built React frontend with TypeScript</li>
</ul>

<h2>Skills</h2>
<p>Python, JavaScript, TypeScript, React, FastAPI, AWS, Docker, Kubernetes</p>

<h2>Education</h2>
<h3>BS Computer Science</h3>
<p>University of California, Berkeley | 2017</p>
"""

SAMPLE_JOB_POSTING = {
    "title": "Senior Backend Engineer",
    "company_name": "Acme Corp",
    "requirements": [
        "5+ years Python experience",
        "Experience with Microservices architecture",
        "Strong knowledge of AWS or GCP",
        "Experience with Kubernetes and Docker",
    ],
    "preferred_qualifications": [
        "Experience with FastAPI or Django",
        "Knowledge of GraphQL",
    ],
    "tech_stack": ["Python", "FastAPI", "AWS", "Kubernetes", "PostgreSQL"],
}

SAMPLE_GAP_ANALYSIS = {
    "keywords_to_include": ["Python", "AWS", "Kubernetes", "microservices", "PostgreSQL"],
}

SAMPLE_USER_PROFILE = {
    "name": "John Doe",
    "email": "john.doe@email.com",
    "phone": "(555) 123-4567",
    "location": "San Francisco, CA",
    "summary": "Experienced software engineer with 8+ years of expertise",
    "skills": ["Python", "JavaScript", "React", "AWS", "Docker"],
    "experience": [
        {
            "company": "Tech Company Inc.",
            "position": "Senior Software Engineer",
            "achievements": [
                "Led development of microservices architecture",
                "Implemented CI/CD pipelines",
            ],
        },
    ],
    "education": [
        {
            "institution": "UC Berkeley",
            "degree": "BS Computer Science",
        },
    ],
}


# ============================================================================
# Export Models Tests
# ============================================================================


class TestExportModels:
    """Tests for export state models."""

    def test_ats_report_creation(self):
        """Test ATSReport model creation."""
        report = ATSReport(
            keyword_match_score=85,
            matched_keywords=["Python", "AWS", "Kubernetes"],
            missing_keywords=["GraphQL"],
            formatting_issues=[],
            recommendations=["Consider adding GraphQL experience"],
        )

        assert report.keyword_match_score == 85
        assert len(report.matched_keywords) == 3
        assert "Python" in report.matched_keywords
        assert report.analyzed_at is not None

    def test_ats_report_default_values(self):
        """Test ATSReport default values."""
        report = ATSReport()

        assert report.keyword_match_score == 0
        assert report.matched_keywords == []
        assert report.missing_keywords == []
        assert report.formatting_issues == []

    def test_linkedin_suggestion_creation(self):
        """Test LinkedInSuggestion model creation."""
        suggestion = LinkedInSuggestion(
            headline="Senior Software Engineer | Python | AWS | Cloud Architecture",
            summary="Experienced engineer passionate about building scalable systems.",
            experience_bullets=[
                {
                    "company": "Tech Corp",
                    "position": "Senior Engineer",
                    "bullets": ["Led team of 5", "Built microservices"],
                },
            ],
        )

        assert "Senior Software Engineer" in suggestion.headline
        assert len(suggestion.experience_bullets) == 1
        assert suggestion.generated_at is not None

    def test_export_output_creation(self):
        """Test ExportOutput model creation."""
        output = ExportOutput(
            pdf_generated=True,
            txt_generated=True,
            json_generated=True,
            export_completed=True,
            completed_at=datetime.now().isoformat(),
        )

        assert output.pdf_generated is True
        assert output.txt_generated is True
        assert output.export_completed is True

    def test_export_output_with_reports(self):
        """Test ExportOutput with embedded reports."""
        ats = ATSReport(keyword_match_score=90)
        linkedin = LinkedInSuggestion(headline="Test Headline")

        output = ExportOutput(
            pdf_generated=True,
            ats_report=ats,
            linkedin_suggestions=linkedin,
            export_completed=True,
        )

        assert output.ats_report.keyword_match_score == 90
        assert output.linkedin_suggestions.headline == "Test Headline"


# ============================================================================
# ATS Optimization Tests
# ============================================================================


class TestATSOptimization:
    """Tests for ATS optimization functionality."""

    def test_optimize_removes_tables(self):
        """Test that tables are converted to paragraphs."""
        html_with_table = """
        <table>
            <tr><td>Skill</td><td>Level</td></tr>
            <tr><td>Python</td><td>Expert</td></tr>
        </table>
        """
        result = optimize_for_ats(html_with_table)

        assert "<table>" not in result
        assert "Python" in result

    def test_optimize_removes_images(self):
        """Test that images are removed or converted to alt text."""
        html_with_image = """
        <p>My photo:</p>
        <img src="photo.jpg" alt="Profile Photo" />
        """
        result = optimize_for_ats(html_with_image)

        assert "<img" not in result
        assert "[Profile Photo]" in result

    def test_optimize_removes_column_styles(self):
        """Test that column-based styles are removed."""
        html_with_columns = """
        <div style="column-count: 2; float: left;">
            <p>Content</p>
        </div>
        """
        result = optimize_for_ats(html_with_columns)

        # The style should be removed
        assert 'style="column' not in result

    def test_optimize_preserves_content(self):
        """Test that optimization preserves text content."""
        result = optimize_for_ats(SAMPLE_RESUME_HTML)

        assert "John Doe" in result
        assert "Senior Software Engineer" in result
        assert "Python" in result


# ============================================================================
# ATS Analysis Tests
# ============================================================================


class TestATSAnalysis:
    """Tests for ATS analysis functionality."""

    def test_analyze_with_matching_keywords(self):
        """Test analysis with keywords that match."""
        keywords = ["Python", "JavaScript", "AWS"]
        report = analyze_ats_compatibility(SAMPLE_RESUME_HTML, keywords)

        assert report.keyword_match_score > 50
        assert "Python" in report.matched_keywords
        assert len(report.missing_keywords) < len(keywords)

    def test_analyze_with_missing_keywords(self):
        """Test analysis identifies missing keywords."""
        keywords = ["Scala", "Rust", "Haskell"]
        report = analyze_ats_compatibility(SAMPLE_RESUME_HTML, keywords)

        assert report.keyword_match_score < 100
        assert len(report.missing_keywords) > 0

    def test_analyze_empty_keywords(self):
        """Test analysis with no keywords returns 100 score."""
        report = analyze_ats_compatibility(SAMPLE_RESUME_HTML, [])

        assert report.keyword_match_score == 100

    def test_analyze_formatting_issues_table(self):
        """Test analysis detects tables."""
        html_with_table = "<table><tr><td>Test</td></tr></table>"
        report = analyze_ats_compatibility(html_with_table, [])

        assert any("table" in issue.lower() for issue in report.formatting_issues)

    def test_analyze_formatting_issues_images(self):
        """Test analysis detects images."""
        html_with_image = '<img src="test.jpg" />'
        report = analyze_ats_compatibility(html_with_image, [])

        assert any("image" in issue.lower() for issue in report.formatting_issues)

    def test_analyze_recommendations_low_score(self):
        """Test analysis provides recommendations for low score."""
        keywords = ["Blockchain", "Solidity", "Web3"]
        report = analyze_ats_compatibility(SAMPLE_RESUME_HTML, keywords)

        assert report.keyword_match_score < 70
        assert len(report.recommendations) > 0

    def test_keyword_extraction(self):
        """Test keyword extraction from job posting."""
        keywords = _extract_job_keywords(SAMPLE_JOB_POSTING, SAMPLE_GAP_ANALYSIS)

        assert "Python" in keywords
        assert "AWS" in keywords
        assert len(keywords) > 0


# ============================================================================
# LinkedIn Suggestions Tests
# ============================================================================


class TestLinkedInSuggestions:
    """Tests for LinkedIn suggestion generation."""

    def test_generate_linkedin_suggestions(self):
        """Test LinkedIn suggestions are generated."""
        suggestions = generate_linkedin_suggestions(
            SAMPLE_RESUME_HTML,
            SAMPLE_USER_PROFILE,
            SAMPLE_JOB_POSTING,
        )

        assert suggestions.headline != ""
        assert suggestions.generated_at is not None

    def test_headline_max_length(self):
        """Test headline respects 220 char limit."""
        long_profile = {
            **SAMPLE_USER_PROFILE,
            "skills": ["Very Long Skill Name " * 10] * 10,
        }
        suggestions = generate_linkedin_suggestions(
            SAMPLE_RESUME_HTML,
            long_profile,
            SAMPLE_JOB_POSTING,
        )

        assert len(suggestions.headline) <= 220

    def test_generate_headline_with_role(self):
        """Test headline generation with current role."""
        headline = _generate_headline(
            "John Doe",
            "Senior Engineer",
            "Staff Engineer",
            {"skills": ["Python", "AWS"]},
        )

        assert "Senior Engineer" in headline

    def test_generate_headline_without_role(self):
        """Test headline generation without current role."""
        headline = _generate_headline(
            "John Doe",
            "",
            "Staff Engineer",
            {"skills": []},
        )

        assert "Aspiring Staff Engineer" in headline

    def test_experience_bullets_extracted(self):
        """Test experience bullets are extracted from profile."""
        suggestions = generate_linkedin_suggestions(
            SAMPLE_RESUME_HTML,
            SAMPLE_USER_PROFILE,
            SAMPLE_JOB_POSTING,
        )

        assert len(suggestions.experience_bullets) > 0
        assert suggestions.experience_bullets[0]["company"] == "Tech Company Inc."


# ============================================================================
# File Generation Tests
# ============================================================================


class TestFileGeneration:
    """Tests for file generation utilities."""

    def test_html_to_text(self):
        """Test HTML to plain text conversion."""
        text = html_to_text(SAMPLE_RESUME_HTML)

        assert "JOHN DOE" in text  # h1 is uppercase
        assert "Senior Software Engineer" in text
        assert "Python" in text

    def test_html_to_text_bullets(self):
        """Test bullet points are converted."""
        text = html_to_text(SAMPLE_RESUME_HTML)

        assert "\u2022" in text  # bullet character

    def test_html_to_json(self):
        """Test HTML to JSON conversion."""
        json_str = html_to_json(SAMPLE_RESUME_HTML, SAMPLE_USER_PROFILE)
        data = json.loads(json_str)

        assert data["name"] == "John Doe"
        assert "email" in data
        assert "experience" in data
        assert "skills" in data

    def test_html_to_json_structure(self):
        """Test JSON has correct structure."""
        json_str = html_to_json(SAMPLE_RESUME_HTML, SAMPLE_USER_PROFILE)
        data = json.loads(json_str)

        assert "generated_at" in data
        assert isinstance(data["experience"], list)
        assert isinstance(data["education"], list)
        assert isinstance(data["skills"], list)

    def test_html_to_docx_generates_bytes(self):
        """Test DOCX generation returns bytes."""
        docx_bytes = html_to_docx(SAMPLE_RESUME_HTML)

        assert isinstance(docx_bytes, bytes)
        assert len(docx_bytes) > 10000  # Should be reasonable size

    def test_html_to_docx_valid_format(self):
        """Test DOCX is valid format (starts with PK - zip signature)."""
        docx_bytes = html_to_docx(SAMPLE_RESUME_HTML)

        # DOCX files are actually ZIP files
        assert docx_bytes[:2] == b"PK"


# ============================================================================
# Score Thresholds Tests
# ============================================================================


class TestScoreThresholds:
    """Tests for ATS score thresholds and warnings."""

    def test_high_score_no_warning(self):
        """Test high score doesn't trigger keyword warning."""
        # Use keywords that are in the resume
        keywords = ["Python", "JavaScript", "AWS", "Docker"]
        report = analyze_ats_compatibility(SAMPLE_RESUME_HTML, keywords)

        # Score should be high
        assert report.keyword_match_score >= 70
        # Shouldn't have "add more keywords" recommendation
        assert not any(
            "add more" in rec.lower()
            for rec in report.recommendations
        )

    def test_low_score_triggers_warning(self):
        """Test low score triggers warning."""
        # Use keywords not in the resume
        keywords = ["Scala", "Rust", "Elixir", "Clojure"]
        report = analyze_ats_compatibility(SAMPLE_RESUME_HTML, keywords)

        assert report.keyword_match_score < 70
        # Should have recommendations
        assert len(report.recommendations) > 0

    def test_score_is_percentage(self):
        """Test score is between 0 and 100."""
        report = analyze_ats_compatibility(SAMPLE_RESUME_HTML, ["Python"])

        assert 0 <= report.keyword_match_score <= 100


# ============================================================================
# Edge Cases
# ============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_html(self):
        """Test handling of empty HTML."""
        report = analyze_ats_compatibility("", [])

        assert report.keyword_match_score == 100  # No keywords to match

    def test_empty_profile(self):
        """Test LinkedIn suggestions with empty profile."""
        suggestions = generate_linkedin_suggestions("<p>Test</p>", {}, {})

        assert suggestions.headline != ""  # Should still generate something

    def test_special_characters_in_content(self):
        """Test handling of special characters."""
        html = "<p>Caf\u00e9 developer - 50% improvement \u2022 \u00a3100k</p>"
        text = html_to_text(html)

        assert "Caf" in text  # Should handle Unicode

    def test_nested_lists(self):
        """Test handling of nested list structures."""
        html = """
        <ul>
            <li>Item 1
                <ul>
                    <li>Nested item</li>
                </ul>
            </li>
        </ul>
        """
        text = html_to_text(html)

        assert "Item 1" in text
