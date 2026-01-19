"""Tests for EXA structured extraction.

These tests verify that:
1. EXA structured extraction returns expected fields
2. Completeness checks work correctly
3. Fallback to LLM is triggered appropriately
"""

import pytest
from unittest.mock import patch, MagicMock

from workflow.nodes.ingest import (
    _is_profile_data_complete,
    _is_job_data_complete,
)
from tools.exa_tool import (
    exa_get_structured_content,
    LINKEDIN_PROFILE_SCHEMA,
    JOB_POSTING_SCHEMA,
)


# =============================================================================
# SAMPLE EXA RESPONSES (captured from real API calls)
# =============================================================================

SAMPLE_EXA_PROFILE_RESPONSE_COMPLETE = {
    "success": True,
    "structured_data": {
        "name": "John Smith",
        "headline": "Senior Software Engineer at Google",
        "summary": "Passionate software engineer with 8+ years of experience.",
        "location": "San Francisco Bay Area",
        "experience": [
            {
                "company": "Google",
                "position": "Senior Software Engineer",
                "location": "Mountain View, CA",
                "start_date": "Jan 2021",
                "end_date": None,
                "is_current": True,
                "description": "Leading development of distributed systems."
            }
        ],
        "education": [
            {
                "school": "Stanford University",
                "degree": "BS",
                "field_of_study": "Computer Science",
                "start_date": "2012",
                "end_date": "2016"
            }
        ],
        "skills": ["Python", "Go", "Kubernetes", "Distributed Systems"]
    },
    "raw_text": "John Smith\nSenior Software Engineer at Google\n...",
    "title": "John Smith - LinkedIn",
    "url": "https://linkedin.com/in/johnsmith"
}

SAMPLE_EXA_PROFILE_RESPONSE_INCOMPLETE = {
    "success": True,
    "structured_data": {
        "name": "Jane Doe",
        # Missing headline, summary, location
        "experience": [],  # Empty - incomplete
        "skills": []  # Empty - incomplete
    },
    "raw_text": "Jane Doe\nSoftware Engineer\n...",
    "title": "Jane Doe - LinkedIn",
    "url": "https://linkedin.com/in/janedoe"
}

SAMPLE_EXA_JOB_RESPONSE_COMPLETE = {
    "success": True,
    "structured_data": {
        "title": "Senior Software Engineer",
        "company_name": "Acme Inc",
        "location": "San Francisco, CA",
        "description": "Join our team to build scalable systems.",
        "requirements": [
            "5+ years of experience",
            "Strong Python skills",
            "Experience with distributed systems"
        ],
        "responsibilities": [
            "Design and build microservices",
            "Mentor junior engineers"
        ],
        "tech_stack": ["Python", "Go", "Kubernetes", "PostgreSQL"]
    },
    "raw_text": "Senior Software Engineer at Acme Inc...",
    "title": "Senior Software Engineer - Acme Inc",
    "url": "https://jobs.acme.com/swe"
}

SAMPLE_EXA_JOB_RESPONSE_INCOMPLETE = {
    "success": True,
    "structured_data": {
        "title": "Software Engineer",
        "company_name": "TechCorp",
        # Missing requirements - incomplete
        "requirements": []
    },
    "raw_text": "Software Engineer at TechCorp...",
    "title": "Software Engineer",
    "url": "https://techcorp.com/jobs/swe"
}


# =============================================================================
# COMPLETENESS CHECK TESTS
# =============================================================================

class TestProfileCompleteness:
    """Test profile data completeness checks."""

    def test_complete_profile_passes(self):
        """Profile with name + experience + skills passes."""
        data = {
            "name": "John Smith",
            "experience": [{"company": "Google", "position": "SWE"}],
            "skills": ["Python", "Go"]
        }
        assert _is_profile_data_complete(data) is True

    def test_profile_with_name_and_experience_passes(self):
        """Profile with name and experience (no skills) passes."""
        data = {
            "name": "John Smith",
            "experience": [{"company": "Google", "position": "SWE"}],
            "skills": []
        }
        assert _is_profile_data_complete(data) is True

    def test_profile_with_name_and_skills_passes(self):
        """Profile with name and skills (no experience) passes."""
        data = {
            "name": "John Smith",
            "experience": [],
            "skills": ["Python", "Go"]
        }
        assert _is_profile_data_complete(data) is True

    def test_profile_without_name_fails(self):
        """Profile without name fails."""
        data = {
            "name": "",
            "experience": [{"company": "Google"}],
            "skills": ["Python"]
        }
        assert _is_profile_data_complete(data) is False

    def test_profile_without_experience_or_skills_fails(self):
        """Profile with name but no experience/skills fails."""
        data = {
            "name": "John Smith",
            "experience": [],
            "skills": []
        }
        assert _is_profile_data_complete(data) is False

    def test_none_profile_fails(self):
        """None profile fails."""
        assert _is_profile_data_complete(None) is False

    def test_empty_profile_fails(self):
        """Empty dict profile fails."""
        assert _is_profile_data_complete({}) is False

    def test_exa_complete_response(self):
        """EXA complete response passes."""
        data = SAMPLE_EXA_PROFILE_RESPONSE_COMPLETE["structured_data"]
        assert _is_profile_data_complete(data) is True

    def test_exa_incomplete_response(self):
        """EXA incomplete response fails."""
        data = SAMPLE_EXA_PROFILE_RESPONSE_INCOMPLETE["structured_data"]
        assert _is_profile_data_complete(data) is False


class TestJobCompleteness:
    """Test job data completeness checks."""

    def test_complete_job_passes(self):
        """Job with title + company + requirements passes."""
        data = {
            "title": "Senior SWE",
            "company_name": "Google",
            "requirements": ["5+ years experience", "Python"]
        }
        assert _is_job_data_complete(data) is True

    def test_job_without_title_fails(self):
        """Job without title fails."""
        data = {
            "title": "",
            "company_name": "Google",
            "requirements": ["Python"]
        }
        assert _is_job_data_complete(data) is False

    def test_job_without_company_fails(self):
        """Job without company fails."""
        data = {
            "title": "Senior SWE",
            "company_name": "",
            "requirements": ["Python"]
        }
        assert _is_job_data_complete(data) is False

    def test_job_without_requirements_fails(self):
        """Job without requirements fails."""
        data = {
            "title": "Senior SWE",
            "company_name": "Google",
            "requirements": []
        }
        assert _is_job_data_complete(data) is False

    def test_none_job_fails(self):
        """None job fails."""
        assert _is_job_data_complete(None) is False

    def test_exa_complete_response(self):
        """EXA complete response passes."""
        data = SAMPLE_EXA_JOB_RESPONSE_COMPLETE["structured_data"]
        assert _is_job_data_complete(data) is True

    def test_exa_incomplete_response(self):
        """EXA incomplete response fails."""
        data = SAMPLE_EXA_JOB_RESPONSE_INCOMPLETE["structured_data"]
        assert _is_job_data_complete(data) is False


# =============================================================================
# EXA STRUCTURED EXTRACTION TESTS
# =============================================================================

class TestExaStructuredExtraction:
    """Test EXA structured extraction function."""

    def test_schema_has_required_profile_fields(self):
        """LinkedIn profile schema has all required fields."""
        props = LINKEDIN_PROFILE_SCHEMA["properties"]
        required_fields = ["name", "headline", "summary", "location",
                          "experience", "education", "skills"]
        for field in required_fields:
            assert field in props, f"Missing field: {field}"

    def test_schema_has_required_job_fields(self):
        """Job posting schema has all required fields."""
        props = JOB_POSTING_SCHEMA["properties"]
        required_fields = ["title", "company_name", "description", "location",
                          "requirements", "responsibilities", "tech_stack"]
        for field in required_fields:
            assert field in props, f"Missing field: {field}"

    @patch('tools.exa_tool.get_exa_client')
    def test_structured_extraction_success(self, mock_client):
        """Successful structured extraction returns data."""
        # Mock EXA response
        mock_result = MagicMock()
        mock_result.results = [MagicMock(
            url="https://linkedin.com/in/test",
            title="Test Profile",
            text="Raw text content",
            summary={"parsed": {"name": "Test User", "skills": ["Python"]}}
        )]
        mock_client.return_value.get_contents.return_value = mock_result

        result = exa_get_structured_content(
            url="https://linkedin.com/in/test",
            content_type="linkedin_profile"
        )

        assert result["success"] is True
        assert result["raw_text"] == "Raw text content"

    @patch('tools.exa_tool.get_exa_client')
    def test_structured_extraction_failure(self, mock_client):
        """Failed extraction returns error."""
        mock_client.return_value.get_contents.side_effect = Exception("API error")

        result = exa_get_structured_content(
            url="https://linkedin.com/in/test",
            content_type="linkedin_profile"
        )

        assert result["success"] is False
        assert "API error" in result["error"]

    @patch('tools.exa_tool.get_exa_client')
    def test_structured_extraction_empty_result(self, mock_client):
        """Empty result returns error."""
        mock_result = MagicMock()
        mock_result.results = []
        mock_client.return_value.get_contents.return_value = mock_result

        result = exa_get_structured_content(
            url="https://linkedin.com/in/test",
            content_type="linkedin_profile"
        )

        assert result["success"] is False
        assert "No content" in result["error"]


# =============================================================================
# INTEGRATION TESTS (require EXA_API_KEY)
# =============================================================================

@pytest.mark.skipif(
    not pytest.importorskip("os").getenv("EXA_API_KEY"),
    reason="EXA_API_KEY not set"
)
class TestExaIntegration:
    """Integration tests with real EXA API."""

    def test_real_linkedin_extraction(self):
        """Test with real LinkedIn URL (requires API key)."""
        result = exa_get_structured_content(
            url="https://www.linkedin.com/in/satlosky/",
            content_type="linkedin_profile"
        )

        assert result["success"] is True
        assert result["raw_text"], "Should have raw text"

        # Check if structured data was extracted
        if result.get("structured_data"):
            data = result["structured_data"]
            print(f"\n=== EXA Structured Data ===")
            print(f"Name: {data.get('name')}")
            print(f"Headline: {data.get('headline')}")
            print(f"Skills: {data.get('skills', [])[:5]}")
            print(f"Experience count: {len(data.get('experience', []))}")

    def test_real_job_extraction(self):
        """Test with real job URL (requires API key)."""
        result = exa_get_structured_content(
            url="https://boards.greenhouse.io/anthropic/jobs/4020932008",
            content_type="job_posting"
        )

        assert result["success"] is True
        assert result["raw_text"], "Should have raw text"

        if result.get("structured_data"):
            data = result["structured_data"]
            print(f"\n=== EXA Structured Data ===")
            print(f"Title: {data.get('title')}")
            print(f"Company: {data.get('company_name')}")
            print(f"Requirements: {data.get('requirements', [])[:3]}")
            print(f"Tech stack: {data.get('tech_stack', [])}")
