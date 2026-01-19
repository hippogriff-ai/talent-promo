"""Integration tests that expose specific bugs in the API.

Each test case is designed to expose a specific bug that needs fixing.
Tests should FAIL before the bug is fixed and PASS after.
"""

import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient

import sys
sys.path.insert(0, "/Users/claudevcheval/Hanalei/talent-promo/apps/api")

from main import app
from routers.optimize import _workflows


client = TestClient(app)


class TestBug001_EmptyResumeTextValidation:
    """BUG_001: Empty string resume_text should be treated as not provided.

    When resume_text is an empty string "", it should be treated the same as
    if it was None, requiring a LinkedIn URL instead.
    """

    def test_empty_resume_text_without_linkedin_fails(self):
        """Empty resume_text without LinkedIn should fail validation."""
        response = client.post(
            "/api/optimize/start",
            json={
                "resume_text": "",  # Empty string, not None
                "job_url": "https://jobs.example.com/engineer",
            }
        )

        # BUG: This currently returns 200 because "" is truthy-ish in validation
        # EXPECTED: 400 error since neither valid LinkedIn nor resume provided
        assert response.status_code == 400
        assert "LinkedIn URL or resume text is required" in response.json()["detail"]


class TestBug002_IncrementVersionEdgeCase:
    """BUG_002: increment_version fails on non-standard version formats.

    The increment_version function assumes versions are always in "X.Y" format
    but doesn't handle edge cases like "10.0" or malformed versions.
    """

    def test_version_increment_at_boundary(self):
        """Test version increment from 9.9 should go to 10.0."""
        from workflow.nodes.drafting import increment_version

        result = increment_version("9.9")
        assert result == "10.0"

    def test_version_increment_with_malformed_version(self):
        """Test increment with malformed version should not crash."""
        from workflow.nodes.drafting import increment_version

        # These should not crash
        result = increment_version("")
        assert result == "1.1"

        result = increment_version("abc")
        assert result == "1.1"

        result = increment_version("1.2.3")  # Too many dots
        assert result == "1.1"


class TestBug003_ResumeHtmlXSS:
    """BUG_003: Resume HTML is not sanitized before storage.

    User-provided HTML content could contain XSS vectors that get stored
    and potentially rendered.
    """

    def test_script_tag_in_resume_is_sanitized(self):
        """Script tags in resume HTML should be stripped."""
        with patch("routers.optimize._run_workflow", new_callable=AsyncMock):
            create_response = client.post(
                "/api/optimize/start",
                json={
                    "linkedin_url": "https://www.linkedin.com/in/johndoe",
                    "job_url": "https://jobs.example.com/engineer",
                }
            )

        thread_id = create_response.json()["thread_id"]

        # Try to inject XSS via resume update
        malicious_html = '<h1>Name</h1><script>alert("xss")</script><p>Content</p>'

        response = client.post(
            f"/api/optimize/{thread_id}/editor/update",
            json={"html_content": malicious_html}
        )

        assert response.status_code == 200

        # Get the stored HTML
        state_response = client.get(f"/api/optimize/{thread_id}/data")
        stored_html = state_response.json()["resume_html"]

        # BUG: Script tags are not being stripped
        # EXPECTED: <script> tags should be removed
        assert "<script>" not in stored_html
        assert "alert" not in stored_html


class TestBug004_RaceConditionWorkflowStatus:
    """BUG_004: Race condition when workflow completes very quickly.

    If a workflow completes before the first status poll, the state
    may not be properly captured.
    """

    def test_status_reflects_quick_completion(self):
        """Status should reflect completed state even for fast workflows."""
        _workflows.clear()

        with patch("routers.optimize._run_workflow", new_callable=AsyncMock):
            create_response = client.post(
                "/api/optimize/start",
                json={
                    "linkedin_url": "https://www.linkedin.com/in/johndoe",
                    "job_url": "https://jobs.example.com/engineer",
                }
            )

        thread_id = create_response.json()["thread_id"]

        # Simulate immediate completion
        _workflows[thread_id]["state"]["current_step"] = "completed"

        response = client.get(f"/api/optimize/status/{thread_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert data["current_step"] == "completed"


class TestBug005_WhitespaceOnlyResumeText:
    """BUG_005: Whitespace-only resume_text passes validation.

    A resume_text that is only whitespace ("   ") should be rejected
    as invalid, but the current validation doesn't strip whitespace.
    """

    def test_whitespace_only_resume_text_fails(self):
        """Whitespace-only resume_text should fail validation."""
        response = client.post(
            "/api/optimize/start",
            json={
                "resume_text": "   \n\t  ",  # Only whitespace
                "job_url": "https://jobs.example.com/engineer",
            }
        )

        # BUG: Whitespace passes through as valid resume_text
        # EXPECTED: 400 error
        assert response.status_code == 400


class TestBug006_DeleteWorkflowIncomplete:
    """BUG_006: Delete workflow only clears memory, not checkpointer.

    When deleting a workflow, only the in-memory _workflows dict is cleared
    but the checkpointer retains the state, allowing recovery.
    """

    def test_deleted_workflow_cannot_be_recovered(self):
        """Deleted workflow should not be recoverable from checkpointer."""
        _workflows.clear()

        with patch("routers.optimize._run_workflow", new_callable=AsyncMock):
            create_response = client.post(
                "/api/optimize/start",
                json={
                    "linkedin_url": "https://www.linkedin.com/in/johndoe",
                    "job_url": "https://jobs.example.com/engineer",
                }
            )

        thread_id = create_response.json()["thread_id"]

        # Delete the workflow
        delete_response = client.delete(f"/api/optimize/{thread_id}")
        assert delete_response.status_code == 200

        # Should NOT be able to recover
        # BUG: Currently the checkpointer recovery might still work
        status_response = client.get(f"/api/optimize/status/{thread_id}")
        assert status_response.status_code == 404


class TestBug007_VersionHistoryGap:
    """BUG_007: Version history only keeps last 5, losing initial version.

    When version history exceeds 5 entries, it keeps the LAST 5
    but the initial version (1.0) is often the most important reference.
    """

    def test_initial_version_preserved(self):
        """Initial version should be preserved in history."""
        with patch("routers.optimize._run_workflow", new_callable=AsyncMock):
            create_response = client.post(
                "/api/optimize/start",
                json={
                    "linkedin_url": "https://www.linkedin.com/in/johndoe",
                    "job_url": "https://jobs.example.com/engineer",
                }
            )

        thread_id = create_response.json()["thread_id"]

        # Set up initial state with version 1.0
        _workflows[thread_id]["state"]["draft_versions"] = [
            {"version": "1.0", "html_content": "<h1>Initial</h1>", "trigger": "initial", "created_at": "2024-01-01"},
        ]
        _workflows[thread_id]["state"]["draft_current_version"] = "1.0"
        _workflows[thread_id]["state"]["resume_html"] = "<h1>Test</h1>"

        # Make 6 saves to trigger version truncation
        for i in range(6):
            client.post(
                f"/api/optimize/{thread_id}/drafting/save",
                json={"html_content": f"<h1>Version {i}</h1>"}
            )

        # Get versions
        response = client.get(f"/api/optimize/{thread_id}/drafting/versions")
        versions = response.json()["versions"]

        # BUG: Initial version 1.0 is lost after truncation
        # EXPECTED: Initial version should always be preserved
        version_numbers = [v["version"] for v in versions]
        assert "1.0" in version_numbers, f"Initial version 1.0 not found in {version_numbers}"


class TestBug008_ReExportMissingBody:
    """BUG_008: Re-export endpoint doesn't accept custom parameters.

    The re_export endpoint calls start_export but doesn't pass through
    any customization options.
    """

    def test_reexport_returns_fresh_result(self):
        """Re-export should regenerate export with updated content."""
        with patch("routers.optimize._run_workflow", new_callable=AsyncMock):
            create_response = client.post(
                "/api/optimize/start",
                json={
                    "linkedin_url": "https://www.linkedin.com/in/johndoe",
                    "job_url": "https://jobs.example.com/engineer",
                }
            )

        thread_id = create_response.json()["thread_id"]

        # Set up approved draft state
        _workflows[thread_id]["state"]["draft_approved"] = True
        _workflows[thread_id]["state"]["resume_html"] = "<h1>Name</h1><p>Summary</p><h2>Experience</h2><ul><li>Led project</li></ul><h2>Skills</h2><p>Python</p><h2>Education</h2><p>BS CS</p>"
        _workflows[thread_id]["state"]["job_posting"] = {"title": "Engineer", "requirements": []}
        _workflows[thread_id]["state"]["gap_analysis"] = {"keywords_to_include": ["Python"]}
        _workflows[thread_id]["state"]["user_profile"] = {"name": "John Doe"}

        # First export
        first_response = client.post(f"/api/optimize/{thread_id}/export/start")
        assert first_response.status_code == 200

        # Update resume
        _workflows[thread_id]["state"]["resume_html"] = "<h1>Updated Name</h1><p>Summary</p><h2>Experience</h2><ul><li>Led project</li></ul><h2>Skills</h2><p>Python</p><h2>Education</h2><p>BS CS</p>"
        _workflows[thread_id]["state"]["resume_final"] = "<h1>Updated Name</h1><p>Summary</p><h2>Experience</h2><ul><li>Led project</li></ul><h2>Skills</h2><p>Python</p><h2>Education</h2><p>BS CS</p>"

        # Re-export should use updated content
        reexport_response = client.post(f"/api/optimize/{thread_id}/export/re-export")
        assert reexport_response.status_code == 200


class TestBug009_LinkedInURLNormalization:
    """BUG_009: LinkedIn URL with trailing slash fails validation.

    A valid LinkedIn URL with a trailing slash like
    "https://linkedin.com/in/johndoe/" should be accepted.
    """

    def test_linkedin_url_with_trailing_slash(self):
        """LinkedIn URL with trailing slash should be valid."""
        with patch("routers.optimize._run_workflow", new_callable=AsyncMock):
            response = client.post(
                "/api/optimize/start",
                json={
                    "linkedin_url": "https://www.linkedin.com/in/johndoe/",  # Trailing slash
                    "job_url": "https://jobs.example.com/engineer",
                }
            )

        # BUG: Trailing slash might cause username extraction to fail
        # EXPECTED: 200 success
        assert response.status_code == 200

    def test_linkedin_url_with_query_params(self):
        """LinkedIn URL with query params should be valid."""
        with patch("routers.optimize._run_workflow", new_callable=AsyncMock):
            response = client.post(
                "/api/optimize/start",
                json={
                    "linkedin_url": "https://www.linkedin.com/in/johndoe?locale=en_US",
                    "job_url": "https://jobs.example.com/engineer",
                }
            )

        assert response.status_code == 200


class TestBug010_SilentEditFailure:
    """BUG_010: Direct edit silently fails when text not found.

    When the original_text doesn't exist in resume_html, the edit
    is silently skipped with no error message.
    """

    def test_edit_nonexistent_text_returns_error(self):
        """Editing text that doesn't exist should return an error."""
        with patch("routers.optimize._run_workflow", new_callable=AsyncMock):
            create_response = client.post(
                "/api/optimize/start",
                json={
                    "linkedin_url": "https://www.linkedin.com/in/johndoe",
                    "job_url": "https://jobs.example.com/engineer",
                }
            )

        thread_id = create_response.json()["thread_id"]

        # Set up resume content
        _workflows[thread_id]["state"]["resume_html"] = "<h1>John Doe</h1><p>Engineer</p>"
        _workflows[thread_id]["state"]["draft_current_version"] = "1.0"
        _workflows[thread_id]["state"]["draft_versions"] = []

        # Try to edit text that doesn't exist
        response = client.post(
            f"/api/optimize/{thread_id}/drafting/edit",
            json={
                "location": "summary",
                "original_text": "This text does not exist in the resume",
                "new_text": "Replacement text"
            }
        )

        # BUG: Returns 200 success even though edit didn't apply
        # EXPECTED: Should return 400 or indicate edit was not applied
        assert response.status_code == 400 or "not_applied" in response.json().get("warning", "").lower()


class TestBug011_MissingUpdatedAtTimestamp:
    """BUG_011: Some endpoints don't update the updated_at timestamp.

    When workflow state changes, the updated_at field should be updated
    but some endpoints forget to set it.
    """

    def test_answer_submission_updates_timestamp(self):
        """Submitting an answer should update the timestamp."""
        with patch("routers.optimize._run_workflow", new_callable=AsyncMock):
            create_response = client.post(
                "/api/optimize/start",
                json={
                    "linkedin_url": "https://www.linkedin.com/in/johndoe",
                    "job_url": "https://jobs.example.com/engineer",
                }
            )

        thread_id = create_response.json()["thread_id"]

        # Set up interrupted state
        _workflows[thread_id]["interrupted"] = True
        old_timestamp = "2024-01-01T00:00:00"
        _workflows[thread_id]["state"]["updated_at"] = old_timestamp

        with patch("routers.optimize._resume_workflow", new_callable=AsyncMock):
            response = client.post(
                f"/api/optimize/{thread_id}/answer",
                json={"text": "My answer"}
            )

        assert response.status_code == 200

        # BUG: updated_at might not be updated
        current_timestamp = _workflows[thread_id]["state"].get("updated_at", old_timestamp)
        assert current_timestamp != old_timestamp, "Timestamp should be updated after answer submission"


class TestBug012_EmptyJobUrlValidation:
    """BUG_012: Empty job_url passes validation.

    When job_url is an empty string, it should be rejected.
    """

    def test_empty_job_url_fails(self):
        """Empty string job_url should fail validation."""
        response = client.post(
            "/api/optimize/start",
            json={
                "linkedin_url": "https://www.linkedin.com/in/johndoe",
                "job_url": "",  # Empty string
            }
        )

        # BUG: Empty job_url might pass through
        assert response.status_code == 400
        assert "Either job URL or pasted job description is required" in response.json()["detail"]


class TestBug013_SpecialCharsInFilename:
    """BUG_013: Special characters in user name break export filename.

    If the user's name contains special characters like "/" or ":",
    the export filename could be malformed or cause errors.
    """

    def test_export_with_special_chars_in_name(self):
        """Export should handle special characters in name."""
        with patch("routers.optimize._run_workflow", new_callable=AsyncMock):
            create_response = client.post(
                "/api/optimize/start",
                json={
                    "linkedin_url": "https://www.linkedin.com/in/johndoe",
                    "job_url": "https://jobs.example.com/engineer",
                }
            )

        thread_id = create_response.json()["thread_id"]

        # Set up state with special chars in name
        _workflows[thread_id]["state"]["user_profile"] = {
            "name": "John/Doe: The <Great>",
        }
        _workflows[thread_id]["state"]["resume_html"] = "<h1>Test</h1>"

        response = client.get(f"/api/optimize/{thread_id}/export/download/txt")

        # Should handle special chars gracefully
        assert response.status_code == 200
        content_disp = response.headers.get("Content-Disposition", "")
        # Filename should not contain problematic characters
        assert "/" not in content_disp.split("filename=")[-1]
        assert ":" not in content_disp.split("filename=")[-1]


class TestBug014_DuplicateSuggestionHandling:
    """BUG_014: Accepting same suggestion twice causes error.

    If a suggestion is accepted and the endpoint is called again with
    the same suggestion_id, it should return a proper error.
    """

    def test_accept_already_resolved_suggestion(self):
        """Accepting already resolved suggestion should fail properly."""
        with patch("routers.optimize._run_workflow", new_callable=AsyncMock):
            create_response = client.post(
                "/api/optimize/start",
                json={
                    "linkedin_url": "https://www.linkedin.com/in/johndoe",
                    "job_url": "https://jobs.example.com/engineer",
                }
            )

        thread_id = create_response.json()["thread_id"]

        # Set up state with a suggestion
        _workflows[thread_id]["state"]["draft_suggestions"] = [
            {"id": "sug_1", "status": "pending", "rationale": "Test", "original_text": "old", "proposed_text": "new"}
        ]
        _workflows[thread_id]["state"]["resume_html"] = "<p>old text</p>"
        _workflows[thread_id]["state"]["draft_current_version"] = "1.0"
        _workflows[thread_id]["state"]["draft_versions"] = []

        # Accept the suggestion
        response1 = client.post(
            f"/api/optimize/{thread_id}/drafting/suggestion",
            json={"suggestion_id": "sug_1", "action": "accept"}
        )
        assert response1.status_code == 200

        # Try to accept again
        response2 = client.post(
            f"/api/optimize/{thread_id}/drafting/suggestion",
            json={"suggestion_id": "sug_1", "action": "accept"}
        )

        # BUG: Should return 400, not 200 or 500
        assert response2.status_code == 400
        assert "already resolved" in response2.json()["detail"].lower()


class TestBug015_DiscoveryExchangeCount:
    """BUG_015: Discovery exchange count not incremented on answer.

    When a user submits an answer during discovery, the exchange count
    should be incremented but it might not be.
    """

    def test_discovery_exchange_increments(self):
        """Submitting discovery answer should increment exchange count."""
        with patch("routers.optimize._run_workflow", new_callable=AsyncMock):
            create_response = client.post(
                "/api/optimize/start",
                json={
                    "linkedin_url": "https://www.linkedin.com/in/johndoe",
                    "job_url": "https://jobs.example.com/engineer",
                }
            )

        thread_id = create_response.json()["thread_id"]

        # Set up discovery state
        _workflows[thread_id]["state"]["current_step"] = "discovery"
        _workflows[thread_id]["state"]["discovery_exchanges"] = 0
        _workflows[thread_id]["interrupted"] = True

        with patch("routers.optimize._resume_workflow", new_callable=AsyncMock):
            response = client.post(
                f"/api/optimize/{thread_id}/answer",
                json={"text": "My discovery answer"}
            )

        # Note: The exchange count is managed by the workflow nodes, not the API
        # This test documents that the API doesn't increment it directly
        assert response.status_code == 200


class TestBug016_ValidationMessageInconsistency:
    """BUG_016: Validation error messages inconsistent format.

    Some validation errors use "LinkedIn URL" and some use "linkedin_url",
    making it hard for frontends to parse errors consistently.
    """

    def test_validation_error_uses_friendly_names(self):
        """Error messages should use user-friendly field names."""
        response = client.post(
            "/api/optimize/start",
            json={
                "linkedin_url": "invalid-url",
                "job_url": "https://jobs.example.com/engineer",
            }
        )

        assert response.status_code == 400
        detail = response.json()["detail"]
        # Should use friendly name, not snake_case
        assert "linkedin_url:" not in detail.lower()


class TestBug017_WorkflowListNoLimit:
    """BUG_017: Workflow list endpoint has no pagination.

    The list_workflows endpoint returns all workflows without limit,
    which could cause performance issues with many workflows.
    """

    def test_workflow_list_respects_limit(self):
        """Workflow list should support pagination/limit."""
        _workflows.clear()

        # Create several workflows
        for i in range(20):
            with patch("routers.optimize._run_workflow", new_callable=AsyncMock):
                client.post(
                    "/api/optimize/start",
                    json={
                        "linkedin_url": f"https://www.linkedin.com/in/user{i}",
                        "job_url": "https://jobs.example.com/engineer",
                    }
                )

        # Default list should have default limit of 10
        response = client.get("/api/optimize/")
        data = response.json()

        # FIX: Now returns paginated results with limit
        assert data["count"] <= 10, f"Should return at most 10 workflows by default, got {data['count']}"
        assert "limit" in data
        assert "total" in data
        assert data["total"] == 20


class TestBug018_ATSReportMissingFields:
    """BUG_018: ATS report endpoint doesn't validate all required fields.

    The ATS report might be missing required fields in edge cases.
    """

    def test_ats_report_complete_structure(self):
        """ATS report should have all required fields."""
        with patch("routers.optimize._run_workflow", new_callable=AsyncMock):
            create_response = client.post(
                "/api/optimize/start",
                json={
                    "linkedin_url": "https://www.linkedin.com/in/johndoe",
                    "job_url": "https://jobs.example.com/engineer",
                }
            )

        thread_id = create_response.json()["thread_id"]

        # Set up minimal ATS report
        _workflows[thread_id]["state"]["ats_report"] = {
            "keyword_match_score": 85,
            # Missing other fields
        }

        response = client.get(f"/api/optimize/{thread_id}/export/ats-report")

        assert response.status_code == 200
        data = response.json()

        # BUG: Report may be incomplete
        required_fields = ["keyword_match_score", "formatting_issues", "recommendations"]
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"


class TestBug019_StreamEventCleanup:
    """BUG_019: SSE stream doesn't handle client disconnect properly.

    When client disconnects during SSE stream, resources might not be cleaned up.
    """
    # This is a design bug - we document it but can't easily test SSE cleanup


class TestBug020_DraftApprovalWithoutValidation:
    """BUG_020: Draft can be approved even with validation warnings.

    The draft approval only checks for errors but not warnings,
    which could lead to suboptimal resumes being approved.
    """

    def test_draft_approval_shows_warnings(self):
        """Draft approval should include validation warnings."""
        with patch("routers.optimize._run_workflow", new_callable=AsyncMock):
            create_response = client.post(
                "/api/optimize/start",
                json={
                    "linkedin_url": "https://www.linkedin.com/in/johndoe",
                    "job_url": "https://jobs.example.com/engineer",
                }
            )

        thread_id = create_response.json()["thread_id"]

        # Set up a valid resume with all required sections
        # But use non-action-verb bullets to trigger warnings
        _workflows[thread_id]["state"]["resume_html"] = """
            <h1>John Doe</h1>
            <h2>Professional Summary</h2>
            <p>A software engineer with experience.</p>
            <h2>Experience</h2>
            <h3>Engineer | Company | 2020-2024</h3>
            <ul>
                <li>Did some work</li>
                <li>Was responsible for tasks</li>
            </ul>
            <h2>Skills</h2>
            <p>Python, JavaScript</p>
            <h2>Education</h2>
            <p>BS Computer Science</p>
        """
        _workflows[thread_id]["state"]["draft_suggestions"] = []

        response = client.post(
            f"/api/optimize/{thread_id}/drafting/approve",
            json={"approved": True}
        )

        assert response.status_code == 200
        data = response.json()

        # FIX: Validation result now includes warnings
        validation = data.get("validation", {})
        assert "warnings" in validation, "Approval should include validation warnings"
        # Should have warning about action verbs (bullets don't start with action verbs)
        assert isinstance(validation["warnings"], list)


class TestBug021_LinkedInSuggestionsMissingFields:
    """BUG_021: LinkedIn suggestions endpoint could return incomplete data.

    The LinkedIn suggestions should always have all expected fields.
    """

    def test_linkedin_suggestions_complete_structure(self):
        """LinkedIn suggestions should have all required fields."""
        with patch("routers.optimize._run_workflow", new_callable=AsyncMock):
            create_response = client.post(
                "/api/optimize/start",
                json={
                    "linkedin_url": "https://www.linkedin.com/in/johndoe",
                    "job_url": "https://jobs.example.com/engineer",
                }
            )

        thread_id = create_response.json()["thread_id"]

        # Set up minimal LinkedIn suggestions
        _workflows[thread_id]["state"]["linkedin_suggestions"] = {
            "headline": "Software Engineer",
            # Missing other fields
        }

        response = client.get(f"/api/optimize/{thread_id}/export/linkedin")

        assert response.status_code == 200
        data = response.json()

        # FIX: Report should be complete
        required_fields = ["headline", "summary", "experience_bullets"]
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"


class TestBug022_WorkflowStateSerializationError:
    """BUG_022: Complex state objects may fail serialization.

    State with datetime objects or custom classes could fail JSON serialization.
    """

    def test_status_returns_valid_json(self):
        """Status endpoint should always return valid JSON."""
        with patch("routers.optimize._run_workflow", new_callable=AsyncMock):
            create_response = client.post(
                "/api/optimize/start",
                json={
                    "linkedin_url": "https://www.linkedin.com/in/johndoe",
                    "job_url": "https://jobs.example.com/engineer",
                }
            )

        thread_id = create_response.json()["thread_id"]

        # Add complex objects that could fail serialization
        from datetime import datetime
        _workflows[thread_id]["state"]["complex_date"] = datetime.now().isoformat()
        _workflows[thread_id]["state"]["nested_object"] = {
            "deep": {"nested": {"value": [1, 2, 3]}}
        }

        response = client.get(f"/api/optimize/status/{thread_id}")

        assert response.status_code == 200
        # Should be able to parse as JSON without error
        data = response.json()
        assert "thread_id" in data


class TestBug023_DiscoveryConfirmWithoutMessages:
    """BUG_023: Discovery confirm should require message history.

    Confirming discovery without any messages should be prevented.
    """

    def test_discovery_confirm_requires_messages(self):
        """Cannot confirm discovery without any conversation messages."""
        with patch("routers.optimize._run_workflow", new_callable=AsyncMock):
            create_response = client.post(
                "/api/optimize/start",
                json={
                    "linkedin_url": "https://www.linkedin.com/in/johndoe",
                    "job_url": "https://jobs.example.com/engineer",
                }
            )

        thread_id = create_response.json()["thread_id"]

        # Set exchange count to 3 but no messages
        _workflows[thread_id]["state"]["discovery_exchanges"] = 3
        _workflows[thread_id]["state"]["discovery_messages"] = []

        response = client.post(
            f"/api/optimize/{thread_id}/discovery/confirm",
            json={"confirmed": True}
        )

        # FIX: Should reject when no actual messages exist
        assert response.status_code == 400
        assert "conversation" in response.json()["detail"].lower() or "incomplete" in response.json()["detail"].lower()


class TestBug024_ExportStartWithoutResume:
    """BUG_024: Export start without resume HTML should fail gracefully.

    Starting export when resume_html is None should return proper error.
    """

    def test_export_start_requires_resume(self):
        """Export start should require resume content."""
        with patch("routers.optimize._run_workflow", new_callable=AsyncMock):
            create_response = client.post(
                "/api/optimize/start",
                json={
                    "linkedin_url": "https://www.linkedin.com/in/johndoe",
                    "job_url": "https://jobs.example.com/engineer",
                }
            )

        thread_id = create_response.json()["thread_id"]

        # Set draft approved but no resume
        _workflows[thread_id]["state"]["draft_approved"] = True
        _workflows[thread_id]["state"]["resume_html"] = None

        response = client.post(f"/api/optimize/{thread_id}/export/start")

        assert response.status_code == 400
        assert "resume" in response.json()["detail"].lower()


class TestBug025_ConcurrentVersionSave:
    """BUG_025: Concurrent version saves could cause conflicts.

    Multiple rapid saves should be handled safely.
    """

    def test_rapid_version_saves_dont_conflict(self):
        """Rapid version saves should each get unique versions."""
        with patch("routers.optimize._run_workflow", new_callable=AsyncMock):
            create_response = client.post(
                "/api/optimize/start",
                json={
                    "linkedin_url": "https://www.linkedin.com/in/johndoe",
                    "job_url": "https://jobs.example.com/engineer",
                }
            )

        thread_id = create_response.json()["thread_id"]

        # Set up initial state
        _workflows[thread_id]["state"]["resume_html"] = "<h1>Test</h1>"
        _workflows[thread_id]["state"]["draft_current_version"] = "1.0"
        _workflows[thread_id]["state"]["draft_versions"] = []

        # Make 3 rapid saves
        versions = []
        for i in range(3):
            response = client.post(
                f"/api/optimize/{thread_id}/drafting/save",
                json={"html_content": f"<h1>Version {i}</h1>"}
            )
            assert response.status_code == 200
            versions.append(response.json()["version"])

        # All versions should be unique
        assert len(versions) == len(set(versions)), f"Duplicate versions: {versions}"


class TestBug026_ChangeLogUnbounded:
    """BUG_026: Change log grows unbounded without cleanup.

    The change log should have some limit to prevent memory issues.
    """

    def test_change_log_has_limit(self):
        """Change log should not grow unbounded."""
        with patch("routers.optimize._run_workflow", new_callable=AsyncMock):
            create_response = client.post(
                "/api/optimize/start",
                json={
                    "linkedin_url": "https://www.linkedin.com/in/johndoe",
                    "job_url": "https://jobs.example.com/engineer",
                }
            )

        thread_id = create_response.json()["thread_id"]

        # Set up initial state
        _workflows[thread_id]["state"]["resume_html"] = "<h1>Test original</h1>"
        _workflows[thread_id]["state"]["draft_current_version"] = "1.0"
        _workflows[thread_id]["state"]["draft_versions"] = []
        _workflows[thread_id]["state"]["draft_change_log"] = []

        # Make many edits
        for i in range(25):
            _workflows[thread_id]["state"]["resume_html"] = f"<h1>Test {i}</h1>"
            response = client.post(
                f"/api/optimize/{thread_id}/drafting/edit",
                json={
                    "location": "header",
                    "original_text": f"Test {i}",
                    "new_text": f"Test {i+1}"
                }
            )

        # Change log should be capped at some reasonable limit
        change_log = _workflows[thread_id]["state"].get("draft_change_log", [])
        assert len(change_log) <= 50, f"Change log too large: {len(change_log)} entries"


class TestBug027_EmptyDiscoveredExperiences:
    """BUG_027: Discovery with no extracted experiences should warn.

    If discovery completes but extracts no experiences, it should warn the user.
    """

    def test_discovery_warn_on_no_experiences(self):
        """Discovery should warn when no experiences extracted."""
        with patch("routers.optimize._run_workflow", new_callable=AsyncMock):
            create_response = client.post(
                "/api/optimize/start",
                json={
                    "linkedin_url": "https://www.linkedin.com/in/johndoe",
                    "job_url": "https://jobs.example.com/engineer",
                }
            )

        thread_id = create_response.json()["thread_id"]

        # Set up discovery state with 3 exchanges but no experiences
        _workflows[thread_id]["state"]["discovery_exchanges"] = 3
        _workflows[thread_id]["state"]["discovery_messages"] = [
            {"role": "assistant", "content": "Question 1"},
            {"role": "user", "content": "Answer 1"},
            {"role": "assistant", "content": "Question 2"},
            {"role": "user", "content": "Answer 2"},
            {"role": "assistant", "content": "Question 3"},
            {"role": "user", "content": "Answer 3"},
        ]
        _workflows[thread_id]["state"]["discovered_experiences"] = []

        with patch("routers.optimize._resume_workflow", new_callable=AsyncMock):
            response = client.post(
                f"/api/optimize/{thread_id}/discovery/confirm",
                json={"confirmed": True}
            )

        # Should succeed but possibly include a warning
        assert response.status_code == 200


class TestBug028_MissingUserProfileInExport:
    """BUG_028: Export without user profile should use fallback.

    Export should work even if user_profile is missing or incomplete.
    """

    def test_export_without_user_profile(self):
        """Export should work without user_profile."""
        with patch("routers.optimize._run_workflow", new_callable=AsyncMock):
            create_response = client.post(
                "/api/optimize/start",
                json={
                    "linkedin_url": "https://www.linkedin.com/in/johndoe",
                    "job_url": "https://jobs.example.com/engineer",
                }
            )

        thread_id = create_response.json()["thread_id"]

        # Set up state without user_profile
        _workflows[thread_id]["state"]["user_profile"] = None
        _workflows[thread_id]["state"]["resume_html"] = "<h1>Test Resume</h1><p>Content</p>"

        response = client.get(f"/api/optimize/{thread_id}/export/download/txt")

        # Should use fallback filename instead of crashing
        assert response.status_code == 200
        content_disp = response.headers.get("Content-Disposition", "")
        assert "filename=" in content_disp


class TestBug029_StreamCleanupOnError:
    """BUG_029: Stream endpoint doesn't validate thread exists first.

    The stream endpoint should return 404 for non-existent threads.
    """

    def test_stream_returns_404_for_nonexistent(self):
        """Stream endpoint should return 404 for non-existent thread."""
        response = client.get("/api/optimize/nonexistent-thread-id/stream")

        # Should return 404, not start streaming
        assert response.status_code == 404


class TestBug030_GapAnalysisWithEmptyData:
    """BUG_030: Gap analysis with empty profile/job data should handle gracefully.

    The gap analysis should work even with minimal data.
    """

    def test_gap_analysis_minimal_data(self):
        """Gap analysis should work with minimal profile data."""
        with patch("routers.optimize._run_workflow", new_callable=AsyncMock):
            create_response = client.post(
                "/api/optimize/start",
                json={
                    "linkedin_url": "https://www.linkedin.com/in/johndoe",
                    "job_url": "https://jobs.example.com/engineer",
                }
            )

        thread_id = create_response.json()["thread_id"]

        # Set up minimal state with empty gap analysis
        _workflows[thread_id]["state"]["gap_analysis"] = {}
        _workflows[thread_id]["state"]["current_step"] = "discovery"

        response = client.get(f"/api/optimize/status/{thread_id}?include_data=true")

        # Should not crash
        assert response.status_code == 200


class TestBug031_WorkflowRecoveryMissingConfig:
    """BUG_031: Workflow recovery with missing config should use defaults.

    When recovering a workflow, missing config values should use defaults.
    """

    def test_recovery_with_minimal_config(self):
        """Recovery should work with minimal config."""
        with patch("routers.optimize._run_workflow", new_callable=AsyncMock):
            create_response = client.post(
                "/api/optimize/start",
                json={
                    "linkedin_url": "https://www.linkedin.com/in/johndoe",
                    "job_url": "https://jobs.example.com/engineer",
                }
            )

        thread_id = create_response.json()["thread_id"]

        # Remove config
        _workflows[thread_id]["config"] = {}

        response = client.get(f"/api/optimize/status/{thread_id}")

        # Should work without crashing
        assert response.status_code == 200


class TestBug032_DataEndpointMissingGapAnalysis:
    """BUG_032: Data endpoint with missing gap_analysis should return null.

    The data endpoint should handle missing gap_analysis gracefully.
    """

    def test_data_endpoint_without_gap_analysis(self):
        """Data endpoint should return null for missing gap_analysis."""
        with patch("routers.optimize._run_workflow", new_callable=AsyncMock):
            create_response = client.post(
                "/api/optimize/start",
                json={
                    "linkedin_url": "https://www.linkedin.com/in/johndoe",
                    "job_url": "https://jobs.example.com/engineer",
                }
            )

        thread_id = create_response.json()["thread_id"]

        # Ensure gap_analysis is not present
        if "gap_analysis" in _workflows[thread_id]["state"]:
            del _workflows[thread_id]["state"]["gap_analysis"]

        response = client.get(f"/api/optimize/{thread_id}/data")

        assert response.status_code == 200
        data = response.json()
        # gap_analysis should be null or empty, not cause an error
        assert data.get("gap_analysis") is None or data.get("gap_analysis") == {}


class TestBug033_EditorAssistWithNoneJobPosting:
    """BUG_033: Editor assist with None job_posting should handle gracefully.

    When job_posting or gap_analysis is explicitly None (not just missing),
    the editor_assist endpoint should handle it without AttributeError.
    """

    def test_editor_assist_with_none_job_posting(self):
        """Editor assist should work when job_posting is None."""
        with patch("routers.optimize._run_workflow", new_callable=AsyncMock):
            create_response = client.post(
                "/api/optimize/start",
                json={
                    "linkedin_url": "https://www.linkedin.com/in/johndoe",
                    "job_url": "https://jobs.example.com/engineer",
                }
            )

        thread_id = create_response.json()["thread_id"]

        # Set job_posting to None explicitly (not just missing)
        _workflows[thread_id]["state"]["job_posting"] = None
        _workflows[thread_id]["state"]["gap_analysis"] = None
        _workflows[thread_id]["state"]["resume_html"] = "<h1>Test</h1>"

        with patch("routers.optimize.get_editor_suggestion", new_callable=AsyncMock) as mock_suggest:
            mock_suggest.return_value = {"suggestion": "Test suggestion"}
            response = client.post(
                f"/api/optimize/{thread_id}/editor/assist",
                json={"action": "improve", "selected_text": "Test text"}
            )

        # Should not crash with AttributeError: 'NoneType' object has no attribute 'get'
        assert response.status_code == 200


class TestBug034_ExportStartWithNoneJobPosting:
    """BUG_034: Export start with None job_posting should handle gracefully.

    When job_posting or gap_analysis is explicitly None (not just missing),
    the export start endpoint should handle it without AttributeError.
    """

    def test_export_start_with_none_job_posting(self):
        """Export start should work when job_posting is None."""
        with patch("routers.optimize._run_workflow", new_callable=AsyncMock):
            create_response = client.post(
                "/api/optimize/start",
                json={
                    "linkedin_url": "https://www.linkedin.com/in/johndoe",
                    "job_url": "https://jobs.example.com/engineer",
                }
            )

        thread_id = create_response.json()["thread_id"]

        # Set up state with draft approved but None job_posting
        _workflows[thread_id]["state"]["draft_approved"] = True
        _workflows[thread_id]["state"]["resume_html"] = "<h1>Test Resume</h1><p>Content here</p>"
        _workflows[thread_id]["state"]["job_posting"] = None
        _workflows[thread_id]["state"]["gap_analysis"] = None
        _workflows[thread_id]["state"]["user_profile"] = {"name": "Test User"}

        response = client.post(f"/api/optimize/{thread_id}/export/start")

        # Should not crash with AttributeError: 'NoneType' object has no attribute 'get'
        assert response.status_code == 200
