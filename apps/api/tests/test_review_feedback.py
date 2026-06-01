from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import pytest
from fastapi.testclient import TestClient

from main import app
from review_feedback import (
    AnthropicRevisionClient,
    FeedbackRevisionRequest,
    FeedbackThreadUpdate,
    InMemoryFeedbackStore,
    LLMRevisionPayload,
    LocalRevisionClient,
    MisconfiguredRevisionClient,
    ProposedRevision,
    ResumeRevisionClient,
    build_llm_revision_payload,
    get_feedback_store,
    get_revision_client,
)

BASE_SNAPSHOT = """ALEX MORGAN
Product Marketing Manager

SUMMARY
Marketing manager with experience launching software products."""

COMPARE_SNAPSHOT = """ALEX MORGAN
Product Marketing Manager

SUMMARY
Product marketer who turns customer insight into practical launch plans."""


def feedback_payload() -> dict[str, object]:
    return {
        "id": "feedback-123",
        "baseVersionId": "original",
        "compareVersionId": "v1",
        "targetVersionId": "v1",
        "lineStart": 5,
        "lineEnd": 5,
        "selectedText": "Product marketer who turns customer insight into practical launch plans.",
        "instruction": "make this punchier and more revenue-specific",
        "baseSnapshot": BASE_SNAPSHOT,
        "compareSnapshot": COMPARE_SNAPSHOT,
        "createdAt": datetime(2026, 5, 19, 4, 0, tzinfo=UTC).isoformat(),
    }


def test_build_llm_payload_contains_exact_feedback_context() -> None:
    request = FeedbackRevisionRequest.model_validate(feedback_payload())

    llm_payload = build_llm_revision_payload(request)
    user_message = llm_payload.messages[1].content

    assert llm_payload.task == "resume_targeted_revision"
    assert llm_payload.response_format["json_schema"]["schema"]["required"] == [
        "proposedRevision",
        "rationale",
    ]
    assert "Line range: 5-5" in user_message
    assert (
        "Product marketer who turns customer insight into practical launch plans."
        in user_message
    )
    assert "make this punchier and more revenue-specific" in user_message
    assert BASE_SNAPSHOT in user_message
    assert COMPARE_SNAPSHOT in user_message
    assert "Do not rewrite unrelated lines" in user_message


def test_revision_client_selection_uses_anthropic_when_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ALLOW_LOCAL_REVISION_FALLBACK", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_MODEL", raising=False)
    monkeypatch.setattr("review_feedback._env_files", lambda: [])

    assert isinstance(get_revision_client(), MisconfiguredRevisionClient)

    monkeypatch.setenv("ALLOW_LOCAL_REVISION_FALLBACK", "1")
    assert isinstance(get_revision_client(), LocalRevisionClient)

    monkeypatch.delenv("ALLOW_LOCAL_REVISION_FALLBACK", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("ANTHROPIC_MODEL", "test-model")
    assert isinstance(get_revision_client(), AnthropicRevisionClient)


def test_revision_client_selection_reads_local_env_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "ANTHROPIC_API_KEY=test-key-from-env-file\n"
        "ANTHROPIC_MODEL=test-model-from-env-file\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("ALLOW_LOCAL_REVISION_FALLBACK", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_MODEL", raising=False)
    monkeypatch.setattr("review_feedback._env_files", lambda: [env_file])

    assert isinstance(get_revision_client(), AnthropicRevisionClient)


def test_rejects_feedback_when_selected_text_is_not_in_generated_snapshot() -> None:
    payload = feedback_payload()
    payload["selectedText"] = "This text is not in the generated resume."

    response = TestClient(app).post("/api/resume/review-feedback/revision", json=payload)

    assert response.status_code == 422
    assert "selectedText must be present in compareSnapshot" in response.text


def test_rejects_invalid_line_range() -> None:
    payload = feedback_payload()
    payload["lineStart"] = 8
    payload["lineEnd"] = 5

    response = TestClient(app).post("/api/resume/review-feedback/revision", json=payload)

    assert response.status_code == 422
    assert "lineEnd must be greater than or equal to lineStart" in response.text


def test_revision_endpoint_reports_missing_anthropic_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ALLOW_LOCAL_REVISION_FALLBACK", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr("review_feedback._env_files", lambda: [])

    response = TestClient(app).post(
        "/api/resume/review-feedback/revision",
        json=feedback_payload(),
    )

    assert response.status_code == 503
    assert "ANTHROPIC_API_KEY" in response.text


def test_revision_endpoint_feeds_structured_payload_to_llm_client() -> None:
    captured: dict[str, object] = {}
    store = InMemoryFeedbackStore()

    class FakeRevisionClient:
        async def propose_revision(
            self,
            request: FeedbackRevisionRequest,
            payload: LLMRevisionPayload,
        ) -> ProposedRevision:
            captured["request"] = request
            captured["payload"] = payload
            return ProposedRevision(
                proposedRevision=(
                    "Product marketing leader connecting customer insight to "
                    "revenue-team launch plans."
                ),
                rationale="Tightens the sentence and adds the requested revenue focus.",
            )

    def override_revision_client() -> ResumeRevisionClient:
        return FakeRevisionClient()

    def override_feedback_store() -> InMemoryFeedbackStore:
        return store

    app.dependency_overrides[get_revision_client] = override_revision_client
    app.dependency_overrides[get_feedback_store] = override_feedback_store
    try:
        response = TestClient(app).post(
            "/api/resume/review-feedback/revision",
            json=feedback_payload(),
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["requestId"] == "feedback-123"
    assert body["targetVersionId"] == "v1"
    assert body["lineStart"] == 5
    assert body["lineEnd"] == 5
    assert (
        body["proposedRevision"]
        == "Product marketing leader connecting customer insight to revenue-team launch plans."
    )
    assert body["rationale"] == "Tightens the sentence and adds the requested revenue focus."
    assert body["llmPayload"]["task"] == "resume_targeted_revision"

    captured_request = captured["request"]
    captured_payload = cast(LLMRevisionPayload, captured["payload"])
    assert isinstance(captured_request, FeedbackRevisionRequest)
    assert captured_request.instruction == "make this punchier and more revenue-specific"
    assert "Current generated text selected by user" in captured_payload.messages[1].content


def test_revision_endpoint_persists_feedback_thread() -> None:
    store = InMemoryFeedbackStore()

    class FakeRevisionClient:
        async def propose_revision(
            self,
            request: FeedbackRevisionRequest,
            payload: LLMRevisionPayload,
        ) -> ProposedRevision:
            assert payload.task == "resume_targeted_revision"
            return ProposedRevision(
                proposedRevision="Revenue-focused customer insight launch plan.",
                rationale="Adds the requested revenue focus.",
            )

    app.dependency_overrides[get_revision_client] = lambda: FakeRevisionClient()
    app.dependency_overrides[get_feedback_store] = lambda: store
    try:
        client = TestClient(app)
        create_response = client.post(
            "/api/resume/review-feedback/revision",
            json=feedback_payload(),
        )
        list_response = client.get(
            "/api/resume/review-feedback/threads",
            params={"targetVersionId": "v1"},
        )
    finally:
        app.dependency_overrides.clear()

    assert create_response.status_code == 200
    assert list_response.status_code == 200
    records = list_response.json()
    assert len(records) == 1
    assert records[0]["id"] == "feedback-123"
    assert records[0]["status"] == "open"
    assert records[0]["request"]["instruction"] == (
        "make this punchier and more revenue-specific"
    )
    assert (
        records[0]["revision"]["proposedRevision"]
        == "Revenue-focused customer insight launch plan."
    )


def test_feedback_thread_status_can_be_updated_after_user_action() -> None:
    store = InMemoryFeedbackStore()

    class FakeRevisionClient:
        async def propose_revision(
            self,
            request: FeedbackRevisionRequest,
            payload: LLMRevisionPayload,
        ) -> ProposedRevision:
            del request, payload
            return ProposedRevision(
                proposedRevision="Revenue-focused customer insight launch plan.",
                rationale="Adds the requested revenue focus.",
            )

    app.dependency_overrides[get_revision_client] = lambda: FakeRevisionClient()
    app.dependency_overrides[get_feedback_store] = lambda: store
    try:
        client = TestClient(app)
        created = client.post("/api/resume/review-feedback/revision", json=feedback_payload())
        assert created.status_code == 200
        updated = client.patch(
            "/api/resume/review-feedback/threads/feedback-123",
            json={"status": "applied", "previousText": COMPARE_SNAPSHOT},
        )
    finally:
        app.dependency_overrides.clear()

    assert updated.status_code == 200
    body = updated.json()
    assert body["status"] == "applied"
    assert body["previousText"] == COMPARE_SNAPSHOT


def test_in_memory_store_returns_none_for_missing_thread_update() -> None:
    store = InMemoryFeedbackStore()

    missing = TestClient(app)
    app.dependency_overrides[get_feedback_store] = lambda: store
    try:
        response = missing.patch(
            "/api/resume/review-feedback/threads/not-found",
            json=FeedbackThreadUpdate(status="applied").model_dump(by_alias=True),
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
