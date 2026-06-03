"""Structured resume document editing endpoints."""

from __future__ import annotations

import logging
import re
import uuid
from typing import Any, Optional

from bs4 import BeautifulSoup
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from guardrails import validate_input
from services.resume_workspace import (
    PatchMismatchError,
    ResumeWorkspaceError,
    ResumeWorkspaceService,
    UnitResolutionError,
    build_edit_plan,
    build_patch,
    build_resume_map,
    render_html,
    resolve_target_unit,
    text_preview,
    unit_label,
    unit_text,
    verify_revision,
)
from workflow.nodes.editor import EDITOR_PROMPTS, get_editor_suggestion

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/resume", tags=["structured-resume"])
workspace_service = ResumeWorkspaceService()


class EditorSelection(BaseModel):
    from_pos: Optional[int] = Field(default=None, alias="from")
    to_pos: Optional[int] = Field(default=None, alias="to")
    context_before: str = ""
    context_after: str = ""


class RevisionRequest(BaseModel):
    user_message: str = ""
    action: Optional[str] = None
    selected_text: str = ""
    editor_selection: Optional[EditorSelection] = None
    current_document_revision_id: Optional[str] = None
    proposed_text: Optional[str] = None
    chat_history: list[dict[str, str]] = Field(default_factory=list)


class ApplyRevisionRequest(BaseModel):
    revision_id: str
    override_verification: bool = False


def _workflow_helpers():
    from routers.optimize import _get_workflow_data, _save_workflow_data

    return _get_workflow_data, _save_workflow_data


def _get_workflow_state(document_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    get_workflow_data, _ = _workflow_helpers()
    workflow_data = get_workflow_data(document_id)
    return workflow_data, workflow_data.get("state", {})


def _save_workflow_state(document_id: str, workflow_data: dict[str, Any], state: dict[str, Any]) -> None:
    _, save_workflow_data = _workflow_helpers()
    workflow_data["state"] = state
    save_workflow_data(document_id, workflow_data)


def _ensure_document_from_workflow(document_id: str) -> dict[str, Any]:
    _, state = _get_workflow_state(document_id)
    html_content = state.get("resume_html") or state.get("resume_final")
    if not html_content:
        raise HTTPException(status_code=404, detail="No resume HTML found for this workflow")
    try:
        return workspace_service.ensure_document(document_id, html_content)
    except ResumeWorkspaceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _job_context(state: dict[str, Any]) -> dict[str, Any]:
    job_posting = state.get("job_posting") or {}
    gap_analysis = state.get("gap_analysis") or {}
    return {
        "title": job_posting.get("title", "") if isinstance(job_posting, dict) else "",
        "company": job_posting.get("company_name", "") if isinstance(job_posting, dict) else "",
        "keywords": gap_analysis.get("keywords_to_include", []) if isinstance(gap_analysis, dict) else [],
    }


def _source_context(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "profile_text": state.get("profile_text", ""),
        "job_text": state.get("job_text", ""),
        "user_profile": state.get("user_profile", {}),
        "job_posting": state.get("job_posting", {}),
        "gap_analysis": state.get("gap_analysis", {}),
        "qa_history": state.get("qa_history", []),
        "research": state.get("research", {}),
        "discovered_experiences": state.get("discovered_experiences", []),
        "user_preferences": state.get("user_preferences"),
    }


def _editor_selection_payload(selection: EditorSelection | None) -> dict[str, Any] | None:
    if selection is None:
        return None
    return selection.model_dump()


def _validate_chat_history(chat_history: list[dict[str, str]], document_id: str) -> list[dict[str, str]]:
    validated: list[dict[str, str]] = []
    for message in chat_history[-12:]:
        role = message.get("role")
        content = message.get("content", "")
        if role not in {"user", "assistant"} or not content:
            continue
        validate_input(content, thread_id=document_id)
        validated.append({"role": role, "content": content})
    return validated


def _action_to_message(action: str | None) -> str:
    messages = {
        "improve": "Improve the selected resume text.",
        "add_keywords": "Add relevant ATS keywords naturally.",
        "quantify": "Add credible metrics or quantification where possible.",
        "shorten": "Make the selected resume text more concise.",
        "rewrite": "Rewrite the selected resume text with fresh language.",
        "fix_tone": "Make the selected resume text more professional and confident.",
        "custom": "Revise the selected resume text according to the user instructions.",
    }
    return messages.get(action or "", "Revise the selected resume text.")


def _plain_resume_text(text: str) -> str:
    cleaned = text.strip()
    if re.search(r"<[a-zA-Z][^>]*>", cleaned):
        cleaned = BeautifulSoup(cleaned, "html.parser").get_text(" ", strip=True)
    cleaned = re.sub(r"```(?:html|text|markdown)?", "", cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.replace("```", "")
    return re.sub(r"\s+", " ", cleaned).strip()


def _target_payload(document: dict[str, Any], target_unit: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": target_unit["id"],
        "kind": target_unit["kind"],
        "label": unit_label(document, target_unit["id"]),
        "text": unit_text(target_unit),
        "textPreview": text_preview(unit_text(target_unit)),
    }


@router.get("/documents/{document_id}/map")
async def get_resume_map(document_id: str):
    """Return a compact address map for a structured resume document."""
    document = _ensure_document_from_workflow(document_id)
    return build_resume_map(document)


@router.post("/documents/{document_id}/plan")
async def plan_resume_revision(document_id: str, request: RevisionRequest):
    """Resolve a request to a target unit and return a read-only edit plan."""
    if request.user_message:
        validate_input(request.user_message, thread_id=document_id)
    if request.selected_text:
        validate_input(request.selected_text, thread_id=document_id)
    if request.proposed_text:
        validate_input(request.proposed_text, thread_id=document_id)

    document = _ensure_document_from_workflow(document_id)
    try:
        target = resolve_target_unit(
            document,
            request.selected_text,
            request.user_message,
            _editor_selection_payload(request.editor_selection),
        )
    except UnitResolutionError as exc:
        return {
            "success": False,
            "error": exc.reason,
            "candidates": exc.candidates,
            "canApply": False,
        }

    user_message = request.user_message or _action_to_message(request.action)
    plan = build_edit_plan(document, target, user_message, request.action)
    return {
        "success": True,
        "documentId": document_id,
        "documentRevisionId": document["revisionId"],
        "targetUnit": _target_payload(document, target),
        "editPlan": plan,
        "canApply": False,
    }


@router.post("/documents/{document_id}/revision")
async def create_resume_revision(document_id: str, request: RevisionRequest):
    """Generate one scoped SEARCH/REPLACE revision proposal for a target unit."""
    if request.user_message:
        validate_input(request.user_message, thread_id=document_id)
    if request.selected_text:
        validate_input(request.selected_text, thread_id=document_id)
    if request.proposed_text:
        validate_input(request.proposed_text, thread_id=document_id)
    chat_history = _validate_chat_history(request.chat_history, document_id)

    workflow_data, state = _get_workflow_state(document_id)
    document = _ensure_document_from_workflow(document_id)
    if (
        request.current_document_revision_id
        and request.current_document_revision_id != document.get("revisionId")
    ):
        raise HTTPException(status_code=409, detail="Resume document revision is stale")

    try:
        target = resolve_target_unit(
            document,
            request.selected_text,
            request.user_message,
            _editor_selection_payload(request.editor_selection),
        )
    except UnitResolutionError as exc:
        return {
            "success": False,
            "error": exc.reason,
            "candidates": exc.candidates,
            "canApply": False,
        }

    user_message = request.user_message or _action_to_message(request.action)
    target_text = unit_text(target)
    plan = build_edit_plan(document, target, user_message, request.action)

    try:
        if request.proposed_text is not None:
            proposed = request.proposed_text
        else:
            action = request.action if request.action in EDITOR_PROMPTS else "custom"
            instructions = user_message if action == "custom" else None
            suggestion = await get_editor_suggestion(
                action=action,
                selected_text=target_text,
                full_resume=render_html(document),
                job_context=_job_context(state),
                instructions=instructions,
                chat_history=chat_history,
                source_context=_source_context(state),
            )
            if not suggestion.get("success"):
                return {
                    "success": False,
                    "error": suggestion.get("error", "Failed to generate revision"),
                    "targetUnit": _target_payload(document, target),
                    "editPlan": plan,
                    "canApply": False,
                }
            proposed = suggestion.get("suggestion", "")
    except Exception as exc:
        logger.exception("Resume revision generation failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    proposed = _plain_resume_text(proposed)
    patch = build_patch(target["id"], target_text, proposed)
    verification = verify_revision(
        before_text=target_text,
        after_text=proposed,
        user_message=user_message,
        action=request.action,
        keywords=_job_context(state).get("keywords", []),
    )

    for todo in plan["todos"]:
        if todo["id"] in {"resolve", "propose", "verify"}:
            todo["status"] = "done"
    for assertion in plan["assertions"]:
        if assertion["id"] == "scope":
            assertion["status"] = "passed"
        elif verification["passed"]:
            assertion["status"] = "passed"
        else:
            assertion["status"] = "needs_review"

    revision_id = f"revision_{uuid.uuid4().hex[:12]}"
    revision = {
        "success": True,
        "documentId": document_id,
        "revisionId": revision_id,
        "documentRevisionId": document["revisionId"],
        "targetUnit": _target_payload(document, target),
        "editPlan": plan,
        "patch": patch,
        "proposedText": proposed,
        "verification": verification,
        "canApply": verification["passed"],
        "overrideRequired": not verification["passed"],
        "userMessage": user_message,
        "action": request.action,
    }
    workspace_service.save_pending_revision(document_id, revision)
    workspace_service.write_progress_for_revision(document_id, revision, "proposed")

    state["resume_document_id"] = document_id
    state["resume_revision_id"] = document["revisionId"]
    _save_workflow_state(document_id, workflow_data, state)
    return revision


@router.post("/documents/{document_id}/apply")
async def apply_resume_revision(document_id: str, request: ApplyRevisionRequest):
    """Apply a previously generated scoped revision and commit it in git."""
    workflow_data, state = _get_workflow_state(document_id)
    _ensure_document_from_workflow(document_id)
    try:
        result = workspace_service.apply_pending_revision(
            document_id,
            request.revision_id,
            allow_verification_override=request.override_verification,
        )
    except PatchMismatchError as exc:
        return {
            "success": False,
            "error": exc.reason,
            "targetUnitId": exc.target_unit_id,
            "currentUnitText": exc.current_text,
            "canApply": False,
        }
    except ResumeWorkspaceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    state["resume_html"] = result["resumeHtml"]
    if state.get("resume_final"):
        state["resume_final"] = result["resumeHtml"]
    state["resume_document_id"] = document_id
    state["resume_revision_id"] = result["document"]["revisionId"]
    history = state.setdefault("suggestion_history", [])
    revision = workspace_service.load_pending_revision(document_id, request.revision_id)
    history.append(
        {
            "original": revision["targetUnit"]["text"],
            "suggestion": revision["proposedText"],
            "user_message": revision["userMessage"],
            "target_unit_id": revision["targetUnit"]["id"],
            "override_verification": request.override_verification,
        }
    )
    _save_workflow_state(document_id, workflow_data, state)

    return {
        "success": True,
        "documentId": document_id,
        "documentRevisionId": result["document"]["revisionId"],
        "resumeHtml": result["resumeHtml"],
        "resumeMarkdown": result["resumeMarkdown"],
        "commit": result["commit"],
        "changedUnitIds": result["changedUnitIds"],
    }


@router.get("/documents/{document_id}/diff")
async def get_resume_diff(document_id: str):
    """Return the git diff for the latest accepted resume edit."""
    _ensure_document_from_workflow(document_id)
    try:
        return workspace_service.diff(document_id)
    except ResumeWorkspaceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/documents/{document_id}/undo")
async def undo_resume_revision(document_id: str):
    """Revert the latest accepted resume edit in the document workspace."""
    workflow_data, state = _get_workflow_state(document_id)
    _ensure_document_from_workflow(document_id)
    try:
        result = workspace_service.undo(document_id)
    except ResumeWorkspaceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    state["resume_html"] = result["resumeHtml"]
    if state.get("resume_final"):
        state["resume_final"] = result["resumeHtml"]
    state["resume_revision_id"] = result["document"]["revisionId"]
    _save_workflow_state(document_id, workflow_data, state)
    return {
        "success": True,
        "documentId": document_id,
        "documentRevisionId": result["document"]["revisionId"],
        "resumeHtml": result["resumeHtml"],
        "resumeMarkdown": result["resumeMarkdown"],
        "commit": result["commit"],
    }
