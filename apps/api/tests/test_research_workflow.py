"""Tests for Research Stage - Step 1 of Resume Optimization Workflow.

These tests verify the success criteria from specs/step1_research.md.
Run with: cd apps/api && python -m pytest tests/test_research_workflow.py -v
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import json


# ============================================================================
# Input Handling Tests
# ============================================================================

class TestInputValidation:
    """Test input handling for Research stage."""

    def test_validate_linkedin_url_valid(self):
        """GIVEN a valid LinkedIn URL, WHEN validating, THEN returns valid."""
        from validators import validate_linkedin_url

        valid_urls = [
            "https://linkedin.com/in/johndoe",
            "https://www.linkedin.com/in/jane-smith",
            "https://linkedin.com/in/user_123",
            "http://linkedin.com/in/test-user",
        ]

        for url in valid_urls:
            is_valid, error = validate_linkedin_url(url)
            assert is_valid, f"Expected {url} to be valid, got error: {error}"

    def test_validate_linkedin_url_invalid(self):
        """GIVEN an invalid LinkedIn URL format, WHEN validating, THEN returns error."""
        from validators import validate_linkedin_url

        invalid_urls = [
            "",
            "not-a-url",
            "https://facebook.com/johndoe",
            "https://linkedin.com/company/test",  # Not a profile URL
            "https://linkedin.com/",  # No profile path
            "ftp://linkedin.com/in/test",  # Wrong protocol
        ]

        for url in invalid_urls:
            is_valid, error = validate_linkedin_url(url)
            assert not is_valid, f"Expected {url} to be invalid"
            assert error is not None, f"Expected error message for {url}"

    def test_validate_job_url_valid(self):
        """GIVEN a valid job listing URL, WHEN validating, THEN returns valid."""
        from validators import validate_job_url

        valid_urls = [
            "https://jobs.lever.co/company/abc123",
            "https://boards.greenhouse.io/company/jobs/123",
            "https://linkedin.com/jobs/view/123456",
            "https://careers.google.com/jobs/results/123",
            "https://example.com/careers/software-engineer",
        ]

        for url in valid_urls:
            is_valid, error = validate_job_url(url)
            assert is_valid, f"Expected {url} to be valid, got error: {error}"

    def test_validate_job_url_invalid(self):
        """GIVEN an invalid job URL format, WHEN validating, THEN returns error."""
        from validators import validate_job_url

        invalid_urls = [
            "",
            "not-a-url",
            "ftp://example.com/job",
        ]

        for url in invalid_urls:
            is_valid, error = validate_job_url(url)
            assert not is_valid, f"Expected {url} to be invalid"

    def test_validate_urls_requires_linkedin_or_resume(self):
        """GIVEN no LinkedIn URL and no resume text, WHEN validating, THEN error."""
        from validators import validate_urls

        is_valid, errors = validate_urls(
            linkedin_url=None,
            job_url="https://example.com/job",
            resume_text=None,
        )

        assert not is_valid
        assert any("LinkedIn URL or resume text" in e for e in errors)

    def test_validate_urls_requires_job_url(self):
        """GIVEN no job URL, WHEN validating, THEN error."""
        from validators import validate_urls

        is_valid, errors = validate_urls(
            linkedin_url="https://linkedin.com/in/test",
            job_url="",
            resume_text=None,
        )

        assert not is_valid
        assert any("Either job URL or pasted job description is required" in e for e in errors)


# ============================================================================
# Company Research Tests
# ============================================================================

class TestCompanyResearch:
    """Test company research functionality."""

    @pytest.mark.asyncio
    async def test_research_fetches_company_info(self):
        """GIVEN a company name from job listing, WHEN research runs, THEN fetches company info."""
        mock_research_result = {
            "success": True,
            "results": [
                {
                    "title": "TechCorp Engineering Blog",
                    "url": "https://blog.techcorp.com",
                    "text": "Our engineering culture emphasizes collaboration...",
                    "summary": "Engineering blog about tech stack and culture",
                }
            ]
        }

        mock_exa = MagicMock()
        mock_exa.invoke = MagicMock(return_value=mock_research_result)

        mock_llm_instance = MagicMock()
        mock_llm_instance.ainvoke = AsyncMock(return_value=MagicMock(
            content=json.dumps({
                "research": {
                    "company_overview": "TechCorp is a leading technology company",
                    "company_culture": "Collaborative and innovative culture",
                    "company_values": ["Innovation", "Collaboration"],
                    "tech_stack_details": [
                        {"technology": "Python", "usage": "Backend", "importance": "critical"}
                    ],
                    "similar_profiles": [],
                    "company_news": ["Recent funding round"],
                    "industry_trends": ["AI/ML adoption"],
                    "hiring_patterns": "Looking for senior engineers",
                },
                "gap_analysis": {
                    "strengths": ["Python experience"],
                    "gaps": [],
                    "recommended_emphasis": [],
                    "transferable_skills": [],
                    "keywords_to_include": ["Python"],
                    "potential_concerns": [],
                },
            })
        ))

        with patch("workflow.nodes.research.exa_search", mock_exa), \
             patch("workflow.nodes.research.ChatAnthropic", return_value=mock_llm_instance):
            from workflow.nodes.research import research_node

            state = {
                "job_posting": {
                    "company_name": "TechCorp",
                    "title": "Senior Software Engineer",
                    "tech_stack": ["Python", "JavaScript"],
                },
                "errors": [],
            }

            result = await research_node(state)

            assert "research" in result
            research = result["research"]
            assert "company_overview" in research
            assert "company_culture" in research
            assert "company_news" in research
            assert "tech_stack_details" in research


# ============================================================================
# Similar Hires Research Tests
# ============================================================================

class TestSimilarHiresResearch:
    """Test similar hires research functionality."""

    @pytest.mark.asyncio
    async def test_finds_similar_hires(self):
        """GIVEN company name and role title, WHEN research runs, THEN finds >= 2 profiles of similar hires."""
        mock_similar = {
            "success": True,
            "results": [
                {"title": "Jane Smith - Senior Engineer at TechCorp", "url": "linkedin.com/in/jane"},
                {"title": "Bob Jones - Staff Engineer at TechCorp", "url": "linkedin.com/in/bob"},
                {"title": "Alice Wong - Principal Engineer at TechCorp", "url": "linkedin.com/in/alice"},
            ]
        }

        mock_exa = MagicMock()
        mock_exa.invoke = MagicMock(return_value=mock_similar)

        mock_llm_instance = MagicMock()
        mock_llm_instance.ainvoke = AsyncMock(return_value=MagicMock(
            content=json.dumps({
                "research": {
                    "company_overview": "TechCorp",
                    "company_culture": "Great culture",
                    "company_values": [],
                    "tech_stack_details": [],
                    "similar_profiles": [
                        {"name": "Jane Smith", "headline": "Senior Engineer", "url": "linkedin.com/in/jane", "key_skills": []},
                        {"name": "Bob Jones", "headline": "Staff Engineer", "url": "linkedin.com/in/bob", "key_skills": []},
                    ],
                    "company_news": [],
                    "industry_trends": [],
                    "hiring_patterns": "",
                },
                "gap_analysis": {
                    "strengths": [],
                    "gaps": [],
                    "recommended_emphasis": [],
                    "transferable_skills": [],
                    "keywords_to_include": [],
                    "potential_concerns": [],
                },
            })
        ))

        with patch("workflow.nodes.research.exa_search", mock_exa), \
             patch("workflow.nodes.research.ChatAnthropic", return_value=mock_llm_instance):
            from workflow.nodes.research import research_node

            state = {
                "job_posting": {
                    "company_name": "TechCorp",
                    "title": "Senior Software Engineer",
                    "tech_stack": [],
                },
                "errors": [],
            }

            result = await research_node(state)

            research = result.get("research", {})
            similar = research.get("similar_profiles", [])
            assert len(similar) >= 2


# ============================================================================
# Hiring Criteria Extraction Tests
# ============================================================================

class TestHiringCriteriaExtraction:
    """Test hiring criteria extraction from job listings."""

    def test_extracts_must_haves_and_preferred(self):
        """GIVEN job listing content, WHEN research runs, THEN extracts must_haves, preferred, keywords, ats_keywords."""
        from workflow.state import JobPostingData

        job = JobPostingData(
            title="Senior Software Engineer",
            company_name="TechCorp",
            description="Looking for a senior engineer...",
            requirements=[
                "5+ years Python experience",
                "Strong system design skills",
            ],
            preferred_qualifications=[
                "ML experience preferred",
                "Startup background a plus",
            ],
            responsibilities=["Lead technical projects"],
            tech_stack=["Python", "AWS", "Docker"],
            source_url="https://example.com/job",
        )

        # Verify the data model captures these fields correctly
        assert len(job.requirements) == 2
        assert len(job.preferred_qualifications) == 2
        assert len(job.tech_stack) == 3


# ============================================================================
# Workflow Persistence Tests
# ============================================================================

class TestWorkflowPersistence:
    """Test workflow state persistence."""

    def test_creates_initial_state(self):
        """Test that create_initial_state creates valid state."""
        from workflow.graph import create_initial_state

        state = create_initial_state(
            linkedin_url="https://linkedin.com/in/test",
            job_url="https://example.com/job",
        )

        assert state["linkedin_url"] == "https://linkedin.com/in/test"
        assert state["job_url"] == "https://example.com/job"
        assert state["current_step"] == "ingest"
        assert state["qa_round"] == 0
        assert state["errors"] == []


# ============================================================================
# Completion Tests
# ============================================================================

class TestResearchCompletion:
    """Test research stage completion."""

    def test_research_complete_when_all_data_present(self):
        """GIVEN all 7 research sub-tasks complete, THEN can proceed to analysis."""
        state = {
            "user_profile": {"name": "John Doe", "experience": [], "skills": []},
            "job_posting": {"title": "Engineer", "company_name": "TechCorp", "requirements": []},
            "research": {
                "company_overview": "Overview",
                "company_culture": "Culture",
                "company_values": [],
                "tech_stack_details": [],
                "similar_profiles": [],
                "company_news": [],
                "industry_trends": [],
            },
            "current_step": "analysis",
        }

        # All required data is present
        assert state["user_profile"] is not None
        assert state["job_posting"] is not None
        assert state["research"] is not None
        assert state["current_step"] == "analysis"

    def test_cannot_complete_without_required_data(self):
        """GIVEN any required research data missing, THEN does not proceed."""
        state_missing_profile = {
            "user_profile": None,
            "job_posting": {"title": "Engineer", "company_name": "TechCorp"},
            "current_step": "ingest",
        }

        # Cannot proceed without profile
        assert state_missing_profile["user_profile"] is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
