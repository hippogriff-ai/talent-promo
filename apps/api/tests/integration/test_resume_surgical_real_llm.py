"""Real-LLM E2E coverage for targeted resume revision mapping.

These tests are opt-in because they call the configured external LLM provider.
Run with:
    RUN_REAL_LLM_TESTS=1 python -m pytest tests/integration/test_resume_surgical_real_llm.py -q
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from main import app
from routers import resume as resume_router
from routers.optimize import _workflows
from services.resume_workspace import ResumeWorkspaceService

pytestmark = [
    pytest.mark.real_llm,
    pytest.mark.skipif(
        os.getenv("RUN_REAL_LLM_TESTS") != "1",
        reason="set RUN_REAL_LLM_TESTS=1 to run real LLM integration tests",
    ),
]


SURGICAL_RESUME_HTML = """
<h1>Jordan Lee</h1>
<p>jordan@example.test • New York, NY • LinkedIn</p>

<h2>Professional Summary</h2>
<p>Senior platform engineer with experience building internal developer tools and distributed services.</p>

<h2>Experience</h2>

<h3>Staff Platform Engineer</h3>
<p><strong>Acme Corp</strong> | 2022 - Present</p>
<ul>
<li>Built internal deployment platform for engineering teams.</li>
<li>Improved API reliability by leading incident reviews and rollout automation.</li>
</ul>

<h3>Senior Backend Engineer</h3>
<p><strong>Beta Inc</strong> | 2019 - 2022</p>
<ul>
<li>Maintained backend services for payments.</li>
</ul>

<h2>Skills</h2>
<p><strong>Languages:</strong> Python, TypeScript | <strong>Cloud:</strong> AWS</p>
"""


def _install_workflow(thread_id: str, workspace_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(resume_router, "workspace_service", ResumeWorkspaceService(workspace_root))
    _workflows[thread_id] = {
        "state": {
            "resume_html": SURGICAL_RESUME_HTML,
            "job_posting": {
                "title": "Staff Platform Engineer",
                "company_name": "Example AI",
            },
            "gap_analysis": {
                "keywords_to_include": ["Kubernetes", "observability", "platform engineering"],
            },
            "profile_text": "Synthetic profile for targeted edit integration tests.",
            "job_text": "Synthetic job requiring Kubernetes, observability, and platform engineering.",
        },
        "config": {},
        "created_at": "2026-01-01T00:00:00",
    }


def _create_revision(client: TestClient, thread_id: str, payload: dict) -> dict:
    response = client.post(f"/api/resume/documents/{thread_id}/revision", json=payload)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["success"] is True, data
    assert data["patch"].startswith(f"targetUnitId: {data['targetUnit']['id']}")
    assert data["proposedText"].strip()
    return data


def _apply_revision(client: TestClient, thread_id: str, revision_id: str) -> dict:
    response = client.post(
        f"/api/resume/documents/{thread_id}/apply",
        json={"revision_id": revision_id},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["success"] is True, data
    return data


def test_selected_beta_payments_bullet_gets_kubernetes_keyword_only(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """A selected single-role bullet should map to that unit and leave other roles untouched."""
    thread_id = f"real-llm-selected-{uuid.uuid4().hex}"
    _install_workflow(thread_id, tmp_path, monkeypatch)
    client = TestClient(app)

    revision = _create_revision(
        client,
        thread_id,
        {
            "action": "custom",
            "selected_text": "Maintained backend services for payments.",
            "user_message": (
                "Add the exact ATS keyword Kubernetes to only this Beta Inc payments bullet. "
                "Keep it as one resume bullet and do not change any other resume text."
            ),
        },
    )

    assert revision["targetUnit"]["id"] == "section.experience.role.1.bullet.0"
    assert "kubernetes" in revision["proposedText"].lower()
    assert revision["verification"]["passed"] is True

    applied = _apply_revision(client, thread_id, revision["revisionId"])

    assert applied["changedUnitIds"] == ["section.experience.role.1.bullet.0"]
    assert "kubernetes" in applied["resumeHtml"].lower()
    assert "Built internal deployment platform for engineering teams." in applied["resumeHtml"]
    assert "Improved API reliability by leading incident reviews and rollout automation." in applied["resumeHtml"]
    assert "Senior platform engineer with experience building internal developer tools" in applied["resumeHtml"]


def test_feedback_second_acme_bullet_gets_observability_keyword_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    """Ordinal feedback like 'second bullet under Acme' should resolve and patch the intended bullet."""
    thread_id = f"real-llm-ordinal-{uuid.uuid4().hex}"
    _install_workflow(thread_id, tmp_path, monkeypatch)
    client = TestClient(app)

    revision = _create_revision(
        client,
        thread_id,
        {
            "action": "custom",
            "selected_text": "",
            "user_message": (
                "Add the exact ATS keyword observability only to the second bullet under Acme Corp. "
                "Keep it one bullet and do not alter the first Acme bullet or the Beta Inc bullet."
            ),
        },
    )

    assert revision["targetUnit"]["id"] == "section.experience.role.0.bullet.1"
    assert "observability" in revision["proposedText"].lower()
    assert revision["verification"]["passed"] is True

    applied = _apply_revision(client, thread_id, revision["revisionId"])

    assert applied["changedUnitIds"] == ["section.experience.role.0.bullet.1"]
    assert "observability" in applied["resumeHtml"].lower()
    assert "Built internal deployment platform for engineering teams." in applied["resumeHtml"]
    assert "Maintained backend services for payments." in applied["resumeHtml"]
    assert "Senior platform engineer with experience building internal developer tools" in applied["resumeHtml"]
