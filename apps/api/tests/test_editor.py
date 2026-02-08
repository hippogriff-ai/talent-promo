"""Tests for editor assist endpoints and functions.

Tests /editor/assist, /editor/sync, /editor/update, /editor/chat,
/editor/regenerate endpoints, and the underlying get_editor_suggestion
and drafting_chat functions.
"""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from fastapi.testclient import TestClient

import sys
sys.path.insert(0, "/Users/claudevcheval/Hanalei/talent-promo/apps/api")

from main import app
from routers.optimize import _workflows

client = TestClient(app)


def _create_workflow_with_state(state_overrides: dict | None = None) -> str:
    """Helper to create a workflow with pre-set state for testing."""
    with (
        patch("routers.optimize._run_workflow", new_callable=AsyncMock),
        patch("routers.optimize.verify_turnstile_token", new_callable=AsyncMock),
    ):
        response = client.post(
            "/api/optimize/start",
            json={
                "linkedin_url": "https://www.linkedin.com/in/testuser",
                "job_url": "https://jobs.example.com/swe",
            },
        )
    assert response.status_code == 200, f"Start failed: {response.status_code} {response.text}"
    thread_id = response.json()["thread_id"]

    # Set up state for editor tests
    base_state = {
        "resume_html": "<h1>Jane Doe</h1><p>Senior engineer with 10 years experience.</p>",
        "job_posting": {"title": "Staff Engineer", "company_name": "Acme Corp"},
        "gap_analysis": {
            "keywords_to_include": ["distributed systems", "leadership", "Python"],
            "strengths": ["backend", "systems design"],
            "recommended_emphasis": ["scalability"],
        },
        "user_profile": {"name": "Jane Doe"},
        "profile_text": "Jane Doe - Senior Engineer",
        "job_text": "Staff Engineer at Acme Corp",
    }
    if state_overrides:
        base_state.update(state_overrides)

    _workflows[thread_id]["state"].update(base_state)
    return thread_id


class TestEditorAssistEndpoint:
    """Tests for POST /{thread_id}/editor/assist."""

    def test_improve_action(self):
        thread_id = _create_workflow_with_state()

        with patch("routers.optimize.get_editor_suggestion", new_callable=AsyncMock) as mock:
            mock.return_value = {"success": True, "suggestion": "Improved text", "action": "improve"}
            response = client.post(
                f"/api/optimize/{thread_id}/editor/assist",
                json={"action": "improve", "selected_text": "Senior engineer with 10 years experience."},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["suggestion"] == "Improved text"

    def test_custom_action_with_instructions(self):
        thread_id = _create_workflow_with_state()

        with patch("routers.optimize.get_editor_suggestion", new_callable=AsyncMock) as mock:
            mock.return_value = {"success": True, "suggestion": "Custom result"}
            response = client.post(
                f"/api/optimize/{thread_id}/editor/assist",
                json={
                    "action": "custom",
                    "selected_text": "Some text",
                    "instructions": "Make it more concise",
                },
            )

        assert response.status_code == 200
        mock.assert_called_once()
        call_kwargs = mock.call_args
        assert call_kwargs[1]["instructions"] == "Make it more concise"

    def test_invalid_action_rejected(self):
        thread_id = _create_workflow_with_state()

        response = client.post(
            f"/api/optimize/{thread_id}/editor/assist",
            json={"action": "invalid_action", "selected_text": "Some text"},
        )

        # Pydantic Literal validation should reject this
        assert response.status_code == 422

    def test_all_valid_actions(self):
        """Each valid action should be accepted by the endpoint."""
        thread_id = _create_workflow_with_state()
        valid_actions = ["improve", "add_keywords", "quantify", "shorten", "rewrite", "fix_tone", "custom"]

        for action in valid_actions:
            with patch("routers.optimize.get_editor_suggestion", new_callable=AsyncMock) as mock:
                mock.return_value = {"success": True, "suggestion": f"{action} result"}
                response = client.post(
                    f"/api/optimize/{thread_id}/editor/assist",
                    json={"action": action, "selected_text": "Test text"},
                )
            assert response.status_code == 200, f"Action '{action}' should be accepted"

    def test_none_job_posting_handled(self):
        """When job_posting is None, should not crash."""
        thread_id = _create_workflow_with_state({"job_posting": None, "gap_analysis": None})

        with patch("routers.optimize.get_editor_suggestion", new_callable=AsyncMock) as mock:
            mock.return_value = {"success": True, "suggestion": "Result"}
            response = client.post(
                f"/api/optimize/{thread_id}/editor/assist",
                json={"action": "improve", "selected_text": "Text"},
            )

        assert response.status_code == 200

    def test_passes_job_context(self):
        thread_id = _create_workflow_with_state()

        with patch("routers.optimize.get_editor_suggestion", new_callable=AsyncMock) as mock:
            mock.return_value = {"success": True, "suggestion": "Result"}
            client.post(
                f"/api/optimize/{thread_id}/editor/assist",
                json={"action": "improve", "selected_text": "Text"},
            )

        call_kwargs = mock.call_args[1]
        assert call_kwargs["job_context"]["title"] == "Staff Engineer"
        assert call_kwargs["job_context"]["company"] == "Acme Corp"
        assert "distributed systems" in call_kwargs["job_context"]["keywords"]

    def test_workflow_not_found(self):
        response = client.post(
            "/api/optimize/nonexistent-thread/editor/assist",
            json={"action": "improve", "selected_text": "Text"},
        )
        assert response.status_code == 404


class TestEditorSyncEndpoint:
    """Tests for POST /{thread_id}/editor/sync."""

    def test_sync_updates_resume_html(self):
        thread_id = _create_workflow_with_state()

        response = client.post(
            f"/api/optimize/{thread_id}/editor/sync",
            json={"html": "<h1>Updated Resume</h1>"},
        )

        assert response.status_code == 200
        assert response.json()["success"] is True
        assert _workflows[thread_id]["state"]["resume_html"] == "<h1>Updated Resume</h1>"

    def test_sync_sanitizes_html(self):
        thread_id = _create_workflow_with_state()

        response = client.post(
            f"/api/optimize/{thread_id}/editor/sync",
            json={"html": '<h1>Test</h1><script>alert("xss")</script>'},
        )

        assert response.status_code == 200
        # Script tags should be stripped (bleach strip=True removes tags, text content stays)
        stored = _workflows[thread_id]["state"]["resume_html"]
        assert "<script>" not in stored

    def test_sync_tracks_suggestion_history(self):
        thread_id = _create_workflow_with_state()

        response = client.post(
            f"/api/optimize/{thread_id}/editor/sync",
            json={
                "html": "<h1>Updated</h1>",
                "original": "old text",
                "suggestion": "new text",
                "user_message": "improve it",
            },
        )

        assert response.status_code == 200
        history = _workflows[thread_id]["state"]["suggestion_history"]
        assert len(history) == 1
        assert history[0]["original"] == "old text"
        assert history[0]["suggestion"] == "new text"
        assert history[0]["user_message"] == "improve it"

    def test_sync_without_suggestion_does_not_track(self):
        thread_id = _create_workflow_with_state()

        client.post(
            f"/api/optimize/{thread_id}/editor/sync",
            json={"html": "<h1>Updated</h1>"},
        )

        history = _workflows[thread_id]["state"].get("suggestion_history", [])
        assert len(history) == 0

    def test_sync_workflow_not_found(self):
        response = client.post(
            "/api/optimize/nonexistent/editor/sync",
            json={"html": "<h1>Test</h1>"},
        )
        assert response.status_code == 404


class TestEditorUpdateEndpoint:
    """Tests for POST /{thread_id}/editor/update."""

    def test_update_saves_html(self):
        thread_id = _create_workflow_with_state()

        response = client.post(
            f"/api/optimize/{thread_id}/editor/update",
            json={"html_content": "<h1>New Resume Content</h1>"},
        )

        assert response.status_code == 200
        state = _workflows[thread_id]["state"]
        assert state["resume_html"] == "<h1>New Resume Content</h1>"
        assert state["resume_final"] == "<h1>New Resume Content</h1>"

    def test_update_sanitizes_html(self):
        thread_id = _create_workflow_with_state()

        response = client.post(
            f"/api/optimize/{thread_id}/editor/update",
            json={"html_content": '<p onclick="alert(1)">Text</p>'},
        )

        assert response.status_code == 200
        stored = _workflows[thread_id]["state"]["resume_html"]
        assert "onclick" not in stored


class TestEditorRegenerateEndpoint:
    """Tests for POST /{thread_id}/editor/regenerate."""

    def test_regenerate_calls_function(self):
        thread_id = _create_workflow_with_state()

        with patch("routers.optimize.regenerate_section", new_callable=AsyncMock) as mock:
            mock.return_value = {"success": True, "section": "summary", "content": "<p>New summary</p>"}
            response = client.post(
                f"/api/optimize/{thread_id}/editor/regenerate",
                json={"section": "summary", "current_content": "<p>Old summary</p>"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["content"] == "<p>New summary</p>"

    def test_regenerate_passes_context(self):
        thread_id = _create_workflow_with_state()

        with patch("routers.optimize.regenerate_section", new_callable=AsyncMock) as mock:
            mock.return_value = {"success": True, "content": "New"}
            client.post(
                f"/api/optimize/{thread_id}/editor/regenerate",
                json={"section": "experience", "current_content": "Old"},
            )

        call_kwargs = mock.call_args[1]
        assert call_kwargs["section"] == "experience"
        assert call_kwargs["user_profile"]["name"] == "Jane Doe"
        assert call_kwargs["job_posting"]["title"] == "Staff Engineer"


class TestEditorChatEndpoint:
    """Tests for POST /{thread_id}/editor/chat."""

    def test_chat_calls_drafting_chat(self):
        thread_id = _create_workflow_with_state()

        with patch("workflow.nodes.drafting.drafting_chat", new_callable=AsyncMock) as mock:
            mock.return_value = {"success": True, "suggestion": "Chat response", "cache_hit": True}
            response = client.post(
                f"/api/optimize/{thread_id}/editor/chat",
                json={
                    "selected_text": "some resume text",
                    "user_message": "make this more impactful",
                    "chat_history": [
                        {"role": "user", "content": "previous question"},
                        {"role": "assistant", "content": "previous answer"},
                    ],
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["suggestion"] == "Chat response"
        assert data["cache_hit"] is True

    def test_chat_passes_state(self):
        thread_id = _create_workflow_with_state()

        with patch("workflow.nodes.drafting.drafting_chat", new_callable=AsyncMock) as mock:
            mock.return_value = {"success": True, "suggestion": "Reply"}
            client.post(
                f"/api/optimize/{thread_id}/editor/chat",
                json={
                    "selected_text": "text",
                    "user_message": "improve",
                    "chat_history": [],
                },
            )

        call_kwargs = mock.call_args[1]
        assert call_kwargs["state"]["resume_html"] is not None
        assert call_kwargs["selected_text"] == "text"
        assert call_kwargs["user_message"] == "improve"

    def test_chat_failure_returns_500(self):
        thread_id = _create_workflow_with_state()

        with patch("workflow.nodes.drafting.drafting_chat", new_callable=AsyncMock) as mock:
            mock.return_value = {"success": False, "error": "LLM timeout"}
            response = client.post(
                f"/api/optimize/{thread_id}/editor/chat",
                json={
                    "selected_text": "text",
                    "user_message": "improve",
                    "chat_history": [],
                },
            )

        assert response.status_code == 500
        assert "LLM timeout" in response.json()["detail"]

    def test_chat_workflow_not_found(self):
        response = client.post(
            "/api/optimize/nonexistent/editor/chat",
            json={
                "selected_text": "text",
                "user_message": "improve",
                "chat_history": [],
            },
        )
        assert response.status_code == 404


class TestDraftingChatFunction:
    """Tests for the drafting_chat function directly."""

    @pytest.mark.asyncio
    async def test_strips_html_from_suggestion(self):
        """Safety net: HTML tags in chat response are stripped to plain text."""
        from workflow.nodes.drafting import drafting_chat

        html_response = '<h2>Professional Summary</h2> <p>Full-stack engineer with 8 years experience.</p>'
        expected_plain = 'Professional Summary Full-stack engineer with 8 years experience.'

        mock_content = MagicMock()
        mock_content.text = html_response

        mock_response = MagicMock()
        mock_response.content = [mock_content]
        mock_response.usage = MagicMock(cache_read_input_tokens=0)

        with patch("workflow.nodes.drafting.get_anthropic_client") as mock_client:
            mock_client.return_value.messages.create.return_value = mock_response
            result = await drafting_chat(
                state={"profile_text": "test", "job_text": "test"},
                selected_text="Full-stack engineer with 6 years",
                user_message="change to 8 years",
                chat_history=[],
            )

        assert result["success"] is True
        assert "<" not in result["suggestion"]
        assert result["suggestion"] == expected_plain

    @pytest.mark.asyncio
    async def test_plain_text_suggestion_unchanged(self):
        """Plain text suggestions pass through without modification."""
        from workflow.nodes.drafting import drafting_chat

        mock_content = MagicMock()
        mock_content.text = "Full-stack engineer with 8 years experience."

        mock_response = MagicMock()
        mock_response.content = [mock_content]
        mock_response.usage = MagicMock(cache_read_input_tokens=100)

        with patch("workflow.nodes.drafting.get_anthropic_client") as mock_client:
            mock_client.return_value.messages.create.return_value = mock_response
            result = await drafting_chat(
                state={"profile_text": "test", "job_text": "test"},
                selected_text="Full-stack engineer with 6 years",
                user_message="change to 8 years",
                chat_history=[],
            )

        assert result["success"] is True
        assert result["suggestion"] == "Full-stack engineer with 8 years experience."
        assert result["cache_hit"] is True


class TestGetEditorSuggestion:
    """Tests for the get_editor_suggestion function."""

    @pytest.mark.asyncio
    async def test_improve_action(self):
        from workflow.nodes.editor import get_editor_suggestion

        mock_response = MagicMock()
        mock_response.content = "Improved version of text"

        with patch("workflow.nodes.editor.get_llm") as mock_llm:
            mock_llm.return_value.ainvoke = AsyncMock(return_value=mock_response)
            result = await get_editor_suggestion(
                action="improve",
                selected_text="Led a team",
                full_resume="<h1>Resume</h1>",
                job_context={"title": "Staff Eng", "company": "Acme", "keywords": ["leadership"]},
            )

        assert result["success"] is True
        assert result["suggestion"] == "Improved version of text"
        assert result["action"] == "improve"

    @pytest.mark.asyncio
    async def test_custom_action_with_instructions(self):
        from workflow.nodes.editor import get_editor_suggestion

        mock_response = MagicMock()
        mock_response.content = "Custom result"

        with patch("workflow.nodes.editor.get_llm") as mock_llm:
            mock_llm.return_value.ainvoke = AsyncMock(return_value=mock_response)
            result = await get_editor_suggestion(
                action="custom",
                selected_text="Some text",
                full_resume="<h1>Resume</h1>",
                job_context={"title": "", "company": "", "keywords": []},
                instructions="Translate to French",
            )

        assert result["success"] is True
        assert result["suggestion"] == "Custom result"

    @pytest.mark.asyncio
    async def test_unknown_action_returns_error(self):
        from workflow.nodes.editor import get_editor_suggestion

        result = await get_editor_suggestion(
            action="nonexistent",
            selected_text="text",
            full_resume="<h1>Resume</h1>",
            job_context={"title": "", "company": "", "keywords": []},
        )

        assert result["success"] is False
        assert "Unknown action" in result["error"]

    @pytest.mark.asyncio
    async def test_llm_error_returns_error(self):
        from workflow.nodes.editor import get_editor_suggestion

        with patch("workflow.nodes.editor.get_llm") as mock_llm:
            mock_llm.return_value.ainvoke = AsyncMock(side_effect=Exception("LLM failed"))
            result = await get_editor_suggestion(
                action="improve",
                selected_text="text",
                full_resume="<h1>Resume</h1>",
                job_context={"title": "", "company": "", "keywords": []},
            )

        assert result["success"] is False
        assert "LLM failed" in result["error"]

    @pytest.mark.asyncio
    async def test_strips_code_blocks_from_response(self):
        from workflow.nodes.editor import get_editor_suggestion

        mock_response = MagicMock()
        mock_response.content = "```html\n<p>Clean text</p>\n```"

        with patch("workflow.nodes.editor.get_llm") as mock_llm:
            mock_llm.return_value.ainvoke = AsyncMock(return_value=mock_response)
            result = await get_editor_suggestion(
                action="improve",
                selected_text="text",
                full_resume="<h1>Resume</h1>",
                job_context={"title": "", "company": "", "keywords": []},
            )

        assert "```" not in result["suggestion"]
        assert "<p>Clean text</p>" in result["suggestion"]


class TestRegenerateSection:
    """Tests for the regenerate_section function."""

    @pytest.mark.asyncio
    async def test_regenerate_summary(self):
        from workflow.nodes.editor import regenerate_section

        mock_response = MagicMock()
        mock_response.content = "<p>New professional summary</p>"

        with patch("workflow.nodes.editor.get_llm") as mock_llm:
            mock_llm.return_value.ainvoke = AsyncMock(return_value=mock_response)
            result = await regenerate_section(
                section="summary",
                current_content="<p>Old summary</p>",
                user_profile={"name": "Jane"},
                job_posting={"title": "Staff Eng", "company_name": "Acme"},
                gap_analysis={"keywords_to_include": ["Python"], "strengths": [], "recommended_emphasis": []},
            )

        assert result["success"] is True
        assert result["section"] == "summary"
        assert "<p>New professional summary</p>" in result["content"]

    @pytest.mark.asyncio
    async def test_regenerate_error(self):
        from workflow.nodes.editor import regenerate_section

        with patch("workflow.nodes.editor.get_llm") as mock_llm:
            mock_llm.return_value.ainvoke = AsyncMock(side_effect=Exception("Timeout"))
            result = await regenerate_section(
                section="experience",
                current_content="<p>Old</p>",
                user_profile={},
                job_posting={},
                gap_analysis={},
            )

        assert result["success"] is False
        assert "Timeout" in result["error"]


class TestHtmlSanitization:
    """Tests for _sanitize_html function."""

    def test_strips_script_tags(self):
        from routers.optimize import _sanitize_html

        result = _sanitize_html('<p>Safe</p><script>alert("xss")</script>')
        assert "<script>" not in result
        # bleach strip=True removes tags but keeps text content
        assert "<p>Safe</p>" in result

    def test_strips_event_handlers(self):
        from routers.optimize import _sanitize_html

        result = _sanitize_html('<p onclick="alert(1)">Text</p>')
        assert "onclick" not in result
        assert "<p>Text</p>" in result

    def test_allows_safe_formatting_tags(self):
        from routers.optimize import _sanitize_html

        html = "<h1>Name</h1><h2>Summary</h2><p><strong>Bold</strong> and <em>italic</em></p><ul><li>Item</li></ul>"
        result = _sanitize_html(html)
        assert "<h1>" in result
        assert "<h2>" in result
        assert "<strong>" in result
        assert "<em>" in result
        assert "<ul>" in result
        assert "<li>" in result

    def test_strips_iframe(self):
        from routers.optimize import _sanitize_html

        result = _sanitize_html('<p>Text</p><iframe src="http://evil.com"></iframe>')
        assert "<iframe" not in result

    def test_allows_links_with_safe_protocols(self):
        from routers.optimize import _sanitize_html

        result = _sanitize_html('<a href="https://example.com">Link</a>')
        assert '<a href="https://example.com">' in result

    def test_strips_javascript_protocol(self):
        from routers.optimize import _sanitize_html

        result = _sanitize_html('<a href="javascript:alert(1)">Link</a>')
        assert "javascript:" not in result
