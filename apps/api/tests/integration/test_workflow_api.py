"""Integration tests for the optimize API endpoints.

These tests exercise the full API flow and expose bugs in:
- URL validation edge cases
- Workflow state management
- Export functionality
- Error handling
"""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from fastapi.testclient import TestClient
from datetime import datetime

import sys
sys.path.insert(0, "/Users/claudevcheval/Hanalei/talent-promo/apps/api")

from main import app


client = TestClient(app)


class TestStartWorkflow:
    """Integration tests for POST /api/optimize/start"""

    def test_start_with_valid_linkedin_and_job_url(self):
        """Test starting workflow with valid URLs."""
        with patch("routers.optimize._run_workflow", new_callable=AsyncMock):
            response = client.post(
                "/api/optimize/start",
                json={
                    "linkedin_url": "https://www.linkedin.com/in/johndoe",
                    "job_url": "https://jobs.example.com/software-engineer",
                }
            )

        assert response.status_code == 200
        data = response.json()
        assert "thread_id" in data
        assert data["current_step"] == "ingest"
        assert data["status"] == "running"

    def test_start_with_resume_text_instead_of_linkedin(self):
        """Test starting workflow with resume text instead of LinkedIn URL."""
        with patch("routers.optimize._run_workflow", new_callable=AsyncMock):
            response = client.post(
                "/api/optimize/start",
                json={
                    "resume_text": "John Doe\nSoftware Engineer\nExperience: ...",
                    "job_url": "https://jobs.example.com/software-engineer",
                }
            )

        assert response.status_code == 200
        data = response.json()
        assert "thread_id" in data

    def test_start_without_linkedin_or_resume_fails(self):
        """BUG_001: Should fail gracefully when neither LinkedIn URL nor resume provided."""
        response = client.post(
            "/api/optimize/start",
            json={
                "job_url": "https://jobs.example.com/software-engineer",
            }
        )

        assert response.status_code == 400
        assert "LinkedIn URL or resume text is required" in response.json()["detail"]

    def test_start_without_job_url_fails(self):
        """Test that missing job URL returns proper error."""
        response = client.post(
            "/api/optimize/start",
            json={
                "linkedin_url": "https://www.linkedin.com/in/johndoe",
            }
        )

        assert response.status_code == 400
        assert "Job URL is required" in response.json()["detail"]

    def test_start_with_invalid_linkedin_url(self):
        """Test that invalid LinkedIn URL is rejected."""
        response = client.post(
            "/api/optimize/start",
            json={
                "linkedin_url": "https://twitter.com/johndoe",
                "job_url": "https://jobs.example.com/software-engineer",
            }
        )

        assert response.status_code == 400
        assert "LinkedIn" in response.json()["detail"]

    def test_start_with_malformed_linkedin_url(self):
        """BUG_002: Test malformed LinkedIn URL (missing /in/ path)."""
        response = client.post(
            "/api/optimize/start",
            json={
                "linkedin_url": "https://www.linkedin.com/company/anthropic",
                "job_url": "https://jobs.example.com/software-engineer",
            }
        )

        assert response.status_code == 400
        assert "profile" in response.json()["detail"].lower()

    def test_start_with_empty_strings(self):
        """BUG_003: Test that empty strings are handled correctly."""
        response = client.post(
            "/api/optimize/start",
            json={
                "linkedin_url": "",
                "job_url": "",
                "resume_text": "",
            }
        )

        assert response.status_code == 400


class TestWorkflowStatus:
    """Integration tests for GET /api/optimize/status/{thread_id}"""

    def test_get_status_for_nonexistent_workflow(self):
        """Test that 404 is returned for non-existent workflow."""
        response = client.get("/api/optimize/status/nonexistent-id")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_get_status_with_include_data(self):
        """Test that include_data flag returns full data."""
        # First create a workflow
        with patch("routers.optimize._run_workflow", new_callable=AsyncMock):
            create_response = client.post(
                "/api/optimize/start",
                json={
                    "linkedin_url": "https://www.linkedin.com/in/johndoe",
                    "job_url": "https://jobs.example.com/software-engineer",
                }
            )

        thread_id = create_response.json()["thread_id"]

        # Get status with include_data
        response = client.get(f"/api/optimize/status/{thread_id}?include_data=true")

        assert response.status_code == 200
        data = response.json()
        # Data fields should be included (even if null)
        assert "user_profile" in data
        assert "job_posting" in data


class TestAnswerSubmission:
    """Integration tests for POST /api/optimize/{thread_id}/answer"""

    def test_submit_answer_when_not_interrupted(self):
        """BUG_004: Should fail when workflow is not waiting for input."""
        # Create a workflow (not interrupted)
        with patch("routers.optimize._run_workflow", new_callable=AsyncMock):
            create_response = client.post(
                "/api/optimize/start",
                json={
                    "linkedin_url": "https://www.linkedin.com/in/johndoe",
                    "job_url": "https://jobs.example.com/software-engineer",
                }
            )

        thread_id = create_response.json()["thread_id"]

        # Try to submit answer when not waiting
        response = client.post(
            f"/api/optimize/{thread_id}/answer",
            json={"text": "My answer"}
        )

        assert response.status_code == 400
        assert "not waiting for input" in response.json()["detail"]

    def test_submit_empty_answer(self):
        """BUG_005: Test submitting empty answer."""
        # Create a workflow and set it to interrupted state
        with patch("routers.optimize._run_workflow", new_callable=AsyncMock):
            create_response = client.post(
                "/api/optimize/start",
                json={
                    "linkedin_url": "https://www.linkedin.com/in/johndoe",
                    "job_url": "https://jobs.example.com/software-engineer",
                }
            )

        thread_id = create_response.json()["thread_id"]

        # Manually set interrupted state
        from routers.optimize import _workflows
        _workflows[thread_id]["interrupted"] = True

        # Submit empty answer
        with patch("routers.optimize._resume_workflow", new_callable=AsyncMock):
            response = client.post(
                f"/api/optimize/{thread_id}/answer",
                json={"text": ""}
            )

        # Should accept empty answer (might be valid in some cases)
        # But frontend should validate this
        assert response.status_code == 200


class TestDiscoveryConfirm:
    """Integration tests for POST /api/optimize/{thread_id}/discovery/confirm"""

    def test_confirm_with_insufficient_exchanges(self):
        """BUG_006: Should reject confirmation with < 3 exchanges."""
        with patch("routers.optimize._run_workflow", new_callable=AsyncMock):
            create_response = client.post(
                "/api/optimize/start",
                json={
                    "linkedin_url": "https://www.linkedin.com/in/johndoe",
                    "job_url": "https://jobs.example.com/software-engineer",
                }
            )

        thread_id = create_response.json()["thread_id"]

        # Set discovery_exchanges to 2 (less than required 3)
        from routers.optimize import _workflows
        _workflows[thread_id]["state"]["discovery_exchanges"] = 2

        response = client.post(
            f"/api/optimize/{thread_id}/discovery/confirm",
            json={"confirmed": True}
        )

        assert response.status_code == 400
        assert "3 conversation exchanges required" in response.json()["detail"]

    def test_confirm_with_minimum_exchanges(self):
        """Test that exactly 3 exchanges is accepted."""
        with patch("routers.optimize._run_workflow", new_callable=AsyncMock):
            create_response = client.post(
                "/api/optimize/start",
                json={
                    "linkedin_url": "https://www.linkedin.com/in/johndoe",
                    "job_url": "https://jobs.example.com/software-engineer",
                }
            )

        thread_id = create_response.json()["thread_id"]

        from routers.optimize import _workflows
        _workflows[thread_id]["state"]["discovery_exchanges"] = 3
        # Must have at least 6 messages (3 questions + 3 answers) for 3 exchanges
        _workflows[thread_id]["state"]["discovery_messages"] = [
            {"role": "assistant", "content": "Question 1"},
            {"role": "user", "content": "Answer 1"},
            {"role": "assistant", "content": "Question 2"},
            {"role": "user", "content": "Answer 2"},
            {"role": "assistant", "content": "Question 3"},
            {"role": "user", "content": "Answer 3"},
        ]

        with patch("routers.optimize._resume_workflow", new_callable=AsyncMock):
            response = client.post(
                f"/api/optimize/{thread_id}/discovery/confirm",
                json={"confirmed": True}
            )

        assert response.status_code == 200


class TestDraftingEndpoints:
    """Integration tests for drafting endpoints."""

    def test_approve_draft_with_pending_suggestions(self):
        """BUG_007: Should reject approval when suggestions are pending."""
        with patch("routers.optimize._run_workflow", new_callable=AsyncMock):
            create_response = client.post(
                "/api/optimize/start",
                json={
                    "linkedin_url": "https://www.linkedin.com/in/johndoe",
                    "job_url": "https://jobs.example.com/software-engineer",
                }
            )

        thread_id = create_response.json()["thread_id"]

        from routers.optimize import _workflows
        _workflows[thread_id]["state"]["draft_suggestions"] = [
            {"id": "sug_1", "status": "pending", "rationale": "Add keywords"}
        ]
        _workflows[thread_id]["state"]["resume_html"] = "<h1>Name</h1><p>Summary</p><h2>Experience</h2><ul><li>Led project</li></ul><h2>Skills</h2><p>Python</p><h2>Education</h2><p>BS CS</p>"

        response = client.post(
            f"/api/optimize/{thread_id}/drafting/approve",
            json={"approved": True}
        )

        assert response.status_code == 400
        assert "pending" in response.json()["detail"].lower()

    def test_restore_nonexistent_version(self):
        """BUG_008: Should return 404 for non-existent version."""
        with patch("routers.optimize._run_workflow", new_callable=AsyncMock):
            create_response = client.post(
                "/api/optimize/start",
                json={
                    "linkedin_url": "https://www.linkedin.com/in/johndoe",
                    "job_url": "https://jobs.example.com/software-engineer",
                }
            )

        thread_id = create_response.json()["thread_id"]

        response = client.post(
            f"/api/optimize/{thread_id}/drafting/restore",
            json={"version": "99.99"}
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_handle_suggestion_not_found(self):
        """Test handling non-existent suggestion."""
        with patch("routers.optimize._run_workflow", new_callable=AsyncMock):
            create_response = client.post(
                "/api/optimize/start",
                json={
                    "linkedin_url": "https://www.linkedin.com/in/johndoe",
                    "job_url": "https://jobs.example.com/software-engineer",
                }
            )

        thread_id = create_response.json()["thread_id"]

        response = client.post(
            f"/api/optimize/{thread_id}/drafting/suggestion",
            json={"suggestion_id": "nonexistent", "action": "accept"}
        )

        assert response.status_code == 404


class TestExportEndpoints:
    """Integration tests for export endpoints."""

    def test_export_without_approved_draft(self):
        """BUG_009: Should reject export when draft not approved."""
        with patch("routers.optimize._run_workflow", new_callable=AsyncMock):
            create_response = client.post(
                "/api/optimize/start",
                json={
                    "linkedin_url": "https://www.linkedin.com/in/johndoe",
                    "job_url": "https://jobs.example.com/software-engineer",
                }
            )

        thread_id = create_response.json()["thread_id"]

        # draft_approved is False by default
        response = client.post(f"/api/optimize/{thread_id}/export/start")

        assert response.status_code == 400
        assert "approved" in response.json()["detail"].lower()

    def test_download_invalid_format(self):
        """BUG_010: Should reject invalid export format."""
        with patch("routers.optimize._run_workflow", new_callable=AsyncMock):
            create_response = client.post(
                "/api/optimize/start",
                json={
                    "linkedin_url": "https://www.linkedin.com/in/johndoe",
                    "job_url": "https://jobs.example.com/software-engineer",
                }
            )

        thread_id = create_response.json()["thread_id"]

        from routers.optimize import _workflows
        _workflows[thread_id]["state"]["resume_html"] = "<h1>Test</h1>"

        response = client.post(f"/api/optimize/{thread_id}/export/download/exe")

        assert response.status_code == 400
        assert "invalid format" in response.json()["detail"].lower()


class TestDeleteWorkflow:
    """Integration tests for DELETE /api/optimize/{thread_id}"""

    def test_delete_nonexistent_workflow(self):
        """Test deleting non-existent workflow returns 404."""
        response = client.delete("/api/optimize/nonexistent-id")

        assert response.status_code == 404

    def test_delete_existing_workflow(self):
        """Test deleting an existing workflow."""
        with patch("routers.optimize._run_workflow", new_callable=AsyncMock):
            create_response = client.post(
                "/api/optimize/start",
                json={
                    "linkedin_url": "https://www.linkedin.com/in/johndoe",
                    "job_url": "https://jobs.example.com/software-engineer",
                }
            )

        thread_id = create_response.json()["thread_id"]

        response = client.delete(f"/api/optimize/{thread_id}")

        assert response.status_code == 200
        assert response.json()["success"] is True

        # Verify workflow is deleted
        get_response = client.get(f"/api/optimize/status/{thread_id}")
        assert get_response.status_code == 404


class TestListWorkflows:
    """Integration tests for GET /api/optimize/"""

    def test_list_workflows_empty(self):
        """Test listing workflows when none exist."""
        from routers.optimize import _workflows
        _workflows.clear()

        response = client.get("/api/optimize/")

        assert response.status_code == 200
        data = response.json()
        assert "workflows" in data
        assert "count" in data
        assert data["count"] == 0

    def test_list_workflows_with_data(self):
        """Test listing workflows returns correct data."""
        from routers.optimize import _workflows
        _workflows.clear()

        with patch("routers.optimize._run_workflow", new_callable=AsyncMock):
            client.post(
                "/api/optimize/start",
                json={
                    "linkedin_url": "https://www.linkedin.com/in/johndoe",
                    "job_url": "https://jobs.example.com/software-engineer",
                }
            )

        response = client.get("/api/optimize/")

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1
        assert len(data["workflows"]) == 1
