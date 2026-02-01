"""Tests for EXA structured extraction.

These tests verify that:
1. EXA structured extraction returns expected fields
2. Schemas have required fields for LinkedIn profiles and job postings
"""

import pytest
from unittest.mock import patch, MagicMock

from tools.exa_tool import (
    exa_get_structured_content,
    LINKEDIN_PROFILE_SCHEMA,
    JOB_POSTING_SCHEMA,
)


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

        # Skip if API call failed (rate limits, network issues, blocked URL, etc.)
        if not result["success"]:
            pytest.skip(f"EXA API unavailable: {result.get('error', 'unknown error')}")

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

        # Skip if API call failed (rate limits, network issues, blocked URL, etc.)
        if not result["success"]:
            pytest.skip(f"EXA API unavailable: {result.get('error', 'unknown error')}")

        assert result["raw_text"], "Should have raw text"

        if result.get("structured_data"):
            data = result["structured_data"]
            print(f"\n=== EXA Structured Data ===")
            print(f"Title: {data.get('title')}")
            print(f"Company: {data.get('company_name')}")
            print(f"Requirements: {data.get('requirements', [])[:3]}")
            print(f"Tech stack: {data.get('tech_stack', [])}")
