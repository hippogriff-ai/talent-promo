import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from main import app
from routers import resume as resume_router
from routers.optimize import _workflows
from services.resume_workspace import (
    PatchMismatchError,
    ResumeWorkspaceService,
    apply_patch_to_document,
    build_patch,
    build_resume_map,
    parse_resume_html,
    render_html,
    resolve_target_unit,
    unit_text,
    verify_revision,
)

SAMPLE_HTML = """
<h1>Jane Doe</h1>
<p>jane@example.com • New York • LinkedIn</p>
<h2>Professional Summary</h2>
<p>Senior engineer with ten years of platform experience.</p>
<h2>Experience</h2>
<h3>Staff Engineer — Platform</h3>
<p><strong>Acme Corp</strong> | 2021 - Present</p>
<ul>
<li>Built internal deployment platform for engineering teams.</li>
<li>Improved API reliability by leading incident reviews and rollout automation.</li>
</ul>
<h3>Senior Engineer</h3>
<p><strong>Beta Inc</strong> | 2018 - 2021</p>
<ul>
<li>Maintained backend services for payments.</li>
</ul>
<h2>Skills</h2>
<p><strong>Languages:</strong> Python, TypeScript | <strong>Cloud:</strong> AWS</p>
"""

DUPLICATE_BULLET_HTML = """
<h1>Jane Doe</h1>
<p>jane@example.com • New York • LinkedIn</p>
<h2>Experience</h2>
<h3>Staff Engineer — Platform</h3>
<p>Acme Corp | 2021 - Present</p>
<ul>
<li>Maintained backend services for payments.</li>
<li>Improved API reliability by leading incident reviews.</li>
</ul>
<h3>Senior Engineer</h3>
<p>Beta Inc | 2018 - 2021</p>
<ul>
<li>Maintained backend services for payments.</li>
</ul>
"""


def test_parse_resume_map_has_addressable_bullets():
    document = parse_resume_html("doc-1", SAMPLE_HTML)
    resume_map = build_resume_map(document)

    unit_ids = {unit["id"] for unit in resume_map["units"]}
    assert "section.experience.role.0.bullet.1" in unit_ids
    assert any(unit["pathLabel"].endswith("Bullet 2") for unit in resume_map["units"])


def test_resolves_second_bullet_under_company_without_full_selection():
    document = parse_resume_html("doc-1", SAMPLE_HTML)

    target = resolve_target_unit(document, user_message="tighten my second bullet under Acme")

    assert target["id"] == "section.experience.role.0.bullet.1"
    assert "API reliability" in unit_text(target)


def test_resolves_under_company_even_when_feedback_mentions_other_role():
    document = parse_resume_html("doc-1", SAMPLE_HTML)

    target = resolve_target_unit(
        document,
        user_message="Add observability only to the second bullet under Acme Corp. Do not alter the Beta Inc bullet.",
    )

    assert target["id"] == "section.experience.role.0.bullet.1"


def test_editor_selection_context_disambiguates_duplicate_text():
    document = parse_resume_html("doc-1", DUPLICATE_BULLET_HTML)

    target = resolve_target_unit(
        document,
        selected_text="Maintained backend services for payments.",
        user_message="make this stronger",
        editor_selection={
            "from": 160,
            "to": 203,
            "context_before": "Senior Engineer Beta Inc | 2018 - 2021",
            "context_after": "",
        },
    )

    assert target["id"] == "section.experience.role.1.bullet.0"


def test_apply_exact_patch_changes_only_target_unit():
    document = parse_resume_html("doc-1", SAMPLE_HTML)
    target = resolve_target_unit(document, selected_text="Built internal deployment platform for engineering teams.")
    patch = build_patch(target["id"], unit_text(target), "Built deployment platform for 40 engineering teams.")
    verification = verify_revision(unit_text(target), "Built deployment platform for 40 engineering teams.", "improve")

    updated = apply_patch_to_document(document, patch, verification=verification)

    html = render_html(updated)
    assert "Built deployment platform for 40 engineering teams." in html
    assert "Improved API reliability" in html


def test_apply_patch_allows_normalized_whitespace_fallback():
    document = parse_resume_html("doc-1", SAMPLE_HTML)
    target = resolve_target_unit(document, selected_text="Maintained backend services for payments.")
    patch = build_patch(target["id"], "Maintained   backend services for payments.", "Maintained payment services.")
    verification = verify_revision(unit_text(target), "Maintained payment services.", "shorten")

    updated = apply_patch_to_document(document, patch, verification=verification)

    assert "Maintained payment services." in render_html(updated)


def test_apply_patch_mismatch_returns_current_unit_text():
    document = parse_resume_html("doc-1", SAMPLE_HTML)
    target = resolve_target_unit(document, selected_text="Maintained backend services for payments.")
    patch = build_patch(target["id"], "Completely different text", "Maintained payment services.")

    with pytest.raises(PatchMismatchError) as exc:
        apply_patch_to_document(document, patch, verification={"passed": True})

    assert exc.value.target_unit_id == target["id"]
    assert "Maintained backend services" in exc.value.current_text


def test_workspace_commit_diff_and_undo(tmp_path: Path):
    if not shutil.which("git"):
        pytest.skip("git is required for workspace versioning")

    service = ResumeWorkspaceService(tmp_path)
    document = service.ensure_document("doc-1", SAMPLE_HTML)
    target = resolve_target_unit(document, selected_text="Built internal deployment platform for engineering teams.")
    proposed = "Built deployment platform for 40 engineering teams."
    revision = {
        "revisionId": "revision-test",
        "targetUnit": {"id": target["id"], "text": unit_text(target)},
        "editPlan": {
            "goal": "improve",
            "targetLabel": "Experience > Acme > Bullet 1",
            "todos": [],
        },
        "patch": build_patch(target["id"], unit_text(target), proposed),
        "proposedText": proposed,
        "verification": verify_revision(unit_text(target), proposed, "improve"),
        "userMessage": "improve",
    }
    service.save_pending_revision("doc-1", revision)

    applied = service.apply_pending_revision("doc-1", "revision-test")

    assert applied["commit"]["sha"]
    assert proposed in service.diff("doc-1")["diff"]

    undone = service.undo("doc-1")
    assert "Built internal deployment platform for engineering teams." in undone["resumeHtml"]


def test_workspace_reparses_when_source_html_changes(tmp_path: Path):
    service = ResumeWorkspaceService(tmp_path)
    original = service.ensure_document("doc-1", SAMPLE_HTML)

    updated_html = SAMPLE_HTML.replace(
        "Senior engineer with ten years of platform experience.",
        "Principal engineer with ten years of platform experience.",
    )
    refreshed = service.ensure_document("doc-1", updated_html)

    assert refreshed["revisionId"] != original["revisionId"]
    assert refreshed["sourceHtmlHash"] != original["sourceHtmlHash"]
    assert "Principal engineer" in render_html(refreshed)


def test_resume_revision_api_apply_updates_workflow_state(tmp_path: Path, monkeypatch):
    if not shutil.which("git"):
        pytest.skip("git is required for workspace versioning")

    monkeypatch.setattr(resume_router, "workspace_service", ResumeWorkspaceService(tmp_path))
    thread_id = "resume-api-thread"
    _workflows[thread_id] = {
        "state": {
            "resume_html": SAMPLE_HTML,
            "job_posting": {"title": "Staff Engineer", "company_name": "Acme"},
            "gap_analysis": {"keywords_to_include": ["platform"]},
        },
        "config": {},
        "created_at": "2026-01-01T00:00:00",
    }
    client = TestClient(app)

    map_response = client.get(f"/api/resume/documents/{thread_id}/map")
    assert map_response.status_code == 200
    assert map_response.json()["documentId"] == thread_id

    revision_response = client.post(
        f"/api/resume/documents/{thread_id}/revision",
        json={
            "selected_text": "Built internal deployment platform for engineering teams.",
            "user_message": "improve",
            "proposed_text": "Built deployment platform for 40 engineering teams.",
        },
    )
    assert revision_response.status_code == 200
    revision = revision_response.json()
    assert revision["success"] is True
    assert revision["canApply"] is True

    apply_response = client.post(
        f"/api/resume/documents/{thread_id}/apply",
        json={"revision_id": revision["revisionId"]},
    )
    assert apply_response.status_code == 200
    assert "40 engineering teams" in apply_response.json()["resumeHtml"]
    assert "40 engineering teams" in _workflows[thread_id]["state"]["resume_html"]


def test_resume_apply_rejects_stale_revision_then_preserves_manual_edits_with_fresh_revision(
    tmp_path: Path,
    monkeypatch,
):
    if not shutil.which("git"):
        pytest.skip("git is required for workspace versioning")

    monkeypatch.setattr(resume_router, "workspace_service", ResumeWorkspaceService(tmp_path))
    thread_id = f"resume-api-manual-sync-thread-{tmp_path.name}"
    _workflows[thread_id] = {
        "state": {
            "resume_html": SAMPLE_HTML,
            "job_posting": {"title": "Staff Engineer", "company_name": "Acme"},
            "gap_analysis": {"keywords_to_include": ["platform"]},
        },
        "config": {},
        "created_at": "2026-01-01T00:00:00",
    }
    client = TestClient(app)
    apply_route = next(
        route
        for route in app.routes
        if getattr(route, "path", "") == "/api/resume/documents/{document_id}/apply"
    )
    assert apply_route.endpoint.__globals__["workspace_service"] is resume_router.workspace_service

    revision_response = client.post(
        f"/api/resume/documents/{thread_id}/revision",
        json={
            "selected_text": "Built internal deployment platform for engineering teams.",
            "user_message": "improve",
            "proposed_text": "Built deployment platform for 40 engineering teams.",
        },
    )
    revision = revision_response.json()
    pending = resume_router.workspace_service.load_pending_revision(thread_id, revision["revisionId"])
    assert pending["documentRevisionId"] == revision["documentRevisionId"]

    synced_html = SAMPLE_HTML.replace(
        "Senior engineer with ten years of platform experience.",
        "Principal engineer with ten years of platform experience.",
    )
    sync_response = client.post(
        f"/api/optimize/{thread_id}/editor/sync",
        json={"html": synced_html},
    )
    assert sync_response.status_code == 200
    assert "Principal engineer with ten years" in _workflows[thread_id]["state"]["resume_html"]

    apply_response = client.post(
        f"/api/resume/documents/{thread_id}/apply",
        json={"revision_id": revision["revisionId"]},
    )

    assert apply_response.status_code == 200
    stale_apply = apply_response.json()
    assert stale_apply["success"] is False
    assert "changed after this revision was generated" in stale_apply["error"]
    assert "Principal engineer with ten years" in _workflows[thread_id]["state"]["resume_html"]

    fresh_revision_response = client.post(
        f"/api/resume/documents/{thread_id}/revision",
        json={
            "selected_text": "Built internal deployment platform for engineering teams.",
            "user_message": "improve",
            "proposed_text": "Built deployment platform for 40 engineering teams.",
        },
    )
    assert fresh_revision_response.status_code == 200
    fresh_revision = fresh_revision_response.json()

    fresh_apply_response = client.post(
        f"/api/resume/documents/{thread_id}/apply",
        json={"revision_id": fresh_revision["revisionId"]},
    )

    assert fresh_apply_response.status_code == 200
    html = fresh_apply_response.json()["resumeHtml"]
    assert "Principal engineer with ten years" in html
    assert "Built deployment platform for 40 engineering teams." in html


def test_resume_revision_passes_chat_history_and_source_context_to_llm(tmp_path: Path, monkeypatch):
    if not shutil.which("git"):
        pytest.skip("git is required for workspace versioning")

    captured: dict = {}

    async def fake_get_editor_suggestion(**kwargs):
        captured.update(kwargs)
        return {
            "success": True,
            "suggestion": "Built deployment platform with clearer, less formal wording.",
        }

    monkeypatch.setattr(resume_router, "workspace_service", ResumeWorkspaceService(tmp_path))
    monkeypatch.setattr(resume_router, "get_editor_suggestion", fake_get_editor_suggestion)
    thread_id = "resume-api-chat-context-thread"
    _workflows[thread_id] = {
        "state": {
            "resume_html": SAMPLE_HTML,
            "profile_text": "Profile source with platform achievements.",
            "job_text": "Job source asks for platform engineering.",
            "job_posting": {"title": "Staff Engineer", "company_name": "Acme"},
            "gap_analysis": {"keywords_to_include": ["platform"]},
        },
        "config": {},
        "created_at": "2026-01-01T00:00:00",
    }
    client = TestClient(app)

    response = client.post(
        f"/api/resume/documents/{thread_id}/revision",
        json={
            "selected_text": "Built internal deployment platform for engineering teams.",
            "user_message": "make that less formal",
            "chat_history": [
                {"role": "user", "content": "Make this more concise first."},
                {"role": "assistant", "content": "Built a concise deployment platform bullet."},
            ],
        },
    )

    assert response.status_code == 200
    assert captured["chat_history"][0]["content"] == "Make this more concise first."
    assert captured["source_context"]["profile_text"] == "Profile source with platform achievements."
    assert captured["source_context"]["job_text"] == "Job source asks for platform engineering."
