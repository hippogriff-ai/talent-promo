from __future__ import annotations

import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any, Literal, Protocol

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

FeedbackThreadStatus = Literal["open", "applied"]
DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-4-6"


class LLMMessage(BaseModel):
    role: Literal["system", "user"]
    content: str


class LLMRevisionPayload(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    task: Literal["resume_targeted_revision"] = "resume_targeted_revision"
    response_format: dict[str, Any] = Field(alias="responseFormat")
    messages: list[LLMMessage]


class FeedbackRevisionRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, str_strip_whitespace=True)

    id: str = Field(min_length=1)
    base_version_id: str = Field(alias="baseVersionId", min_length=1)
    compare_version_id: str = Field(alias="compareVersionId", min_length=1)
    target_version_id: str = Field(alias="targetVersionId", min_length=1)
    line_start: int = Field(alias="lineStart", ge=1)
    line_end: int = Field(alias="lineEnd", ge=1)
    selected_text: str = Field(alias="selectedText", min_length=1)
    instruction: str = Field(min_length=1)
    base_snapshot: str = Field(alias="baseSnapshot", min_length=1)
    compare_snapshot: str = Field(alias="compareSnapshot", min_length=1)
    created_at: datetime = Field(alias="createdAt")

    @model_validator(mode="after")
    def validate_revision_context(self) -> "FeedbackRevisionRequest":
        if self.line_end < self.line_start:
            raise ValueError("lineEnd must be greater than or equal to lineStart")

        if (
            self.selected_text != "Blank line"
            and _normalize(self.selected_text) not in _normalize(self.compare_snapshot)
        ):
            raise ValueError("selectedText must be present in compareSnapshot")

        return self


class ProposedRevision(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    proposed_revision: str = Field(alias="proposedRevision")
    rationale: str


class FeedbackRevisionResponse(ProposedRevision):
    model_config = ConfigDict(populate_by_name=True)

    request_id: str = Field(alias="requestId")
    target_version_id: str = Field(alias="targetVersionId")
    line_start: int = Field(alias="lineStart")
    line_end: int = Field(alias="lineEnd")
    llm_payload: LLMRevisionPayload = Field(alias="llmPayload")


class FeedbackThreadRecord(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    request: FeedbackRevisionRequest
    revision: FeedbackRevisionResponse
    status: FeedbackThreadStatus
    previous_text: str | None = Field(default=None, alias="previousText")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")


class FeedbackThreadUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    status: FeedbackThreadStatus
    previous_text: str | None = Field(default=None, alias="previousText")


class RevisionClientError(RuntimeError):
    pass


class ResumeRevisionClient(Protocol):
    async def propose_revision(
        self,
        request: FeedbackRevisionRequest,
        payload: LLMRevisionPayload,
    ) -> ProposedRevision:
        """Return the proposed replacement for the selected generated text."""


class LocalRevisionClient:
    async def propose_revision(
        self,
        request: FeedbackRevisionRequest,
        payload: LLMRevisionPayload,
    ) -> ProposedRevision:
        del payload
        return ProposedRevision(
            proposedRevision=_fallback_revision(request),
            rationale=(
                "Local deterministic fallback. Replace this client with the hosted LLM adapter."
            ),
        )


class AnthropicRevisionClient:
    def __init__(self, api_key: str, model: str) -> None:
        self._api_key = api_key
        self._model = model

    async def propose_revision(
        self,
        request: FeedbackRevisionRequest,
        payload: LLMRevisionPayload,
    ) -> ProposedRevision:
        del request
        system_prompt = "\n\n".join(
            message.content for message in payload.messages if message.role == "system"
        )
        user_prompt = "\n\n".join(
            message.content for message in payload.messages if message.role == "user"
        )
        tool_name = "propose_resume_revision"

        try:
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                        "x-api-key": self._api_key,
                    },
                    json={
                        "max_tokens": 512,
                        "messages": [{"role": "user", "content": user_prompt}],
                        "model": self._model,
                        "system": system_prompt,
                        "temperature": 0.2,
                        "tool_choice": {"type": "tool", "name": tool_name},
                        "tools": [
                            {
                                "name": tool_name,
                                "description": (
                                    "Return the targeted resume replacement and "
                                    "one concise rationale."
                                ),
                                "input_schema": payload.response_format["json_schema"][
                                    "schema"
                                ],
                            },
                        ],
                    },
                )
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise RevisionClientError("Anthropic revision request failed") from exc

        try:
            message = response.json()
            raw_revision = _extract_anthropic_tool_input(message, tool_name)
            return ProposedRevision.model_validate(raw_revision)
        except (KeyError, TypeError, ValidationError) as exc:
            raise RevisionClientError(
                "Anthropic revision response did not include a valid tool result"
            ) from exc


class MissingRevisionClientConfig(RevisionClientError):
    pass


class MisconfiguredRevisionClient:
    async def propose_revision(
        self,
        request: FeedbackRevisionRequest,
        payload: LLMRevisionPayload,
    ) -> ProposedRevision:
        del request, payload
        raise MissingRevisionClientConfig(
            "ANTHROPIC_API_KEY is required for real revision generation."
        )


class FeedbackStore(Protocol):
    async def save(
        self,
        request: FeedbackRevisionRequest,
        revision: FeedbackRevisionResponse,
    ) -> FeedbackThreadRecord:
        """Persist a generated targeted feedback revision."""

    async def list(
        self,
        target_version_id: str | None = None,
    ) -> list[FeedbackThreadRecord]:
        """Return stored feedback records."""

    async def update(
        self,
        request_id: str,
        update: FeedbackThreadUpdate,
    ) -> FeedbackThreadRecord | None:
        """Update review-thread state after the user applies or reopens it."""


class InMemoryFeedbackStore:
    def __init__(self) -> None:
        self._records: dict[str, FeedbackThreadRecord] = {}

    async def save(
        self,
        request: FeedbackRevisionRequest,
        revision: FeedbackRevisionResponse,
    ) -> FeedbackThreadRecord:
        now = _utcnow()
        record = FeedbackThreadRecord(
            id=request.id,
            request=request,
            revision=revision,
            status="open",
            createdAt=now,
            updatedAt=now,
        )
        self._records[request.id] = record
        return record

    async def list(
        self,
        target_version_id: str | None = None,
    ) -> list[FeedbackThreadRecord]:
        records = sorted(
            self._records.values(),
            key=lambda record: record.created_at,
        )

        if target_version_id is None:
            return records

        return [
            record
            for record in records
            if record.request.target_version_id == target_version_id
        ]

    async def update(
        self,
        request_id: str,
        update: FeedbackThreadUpdate,
    ) -> FeedbackThreadRecord | None:
        record = self._records.get(request_id)
        if record is None:
            return None

        next_record = record.model_copy(
            update={
                "status": update.status,
                "previous_text": update.previous_text,
                "updated_at": _utcnow(),
            },
        )
        self._records[request_id] = next_record
        return next_record


_feedback_store = InMemoryFeedbackStore()


def get_revision_client() -> ResumeRevisionClient:
    if _get_env("ALLOW_LOCAL_REVISION_FALLBACK") == "1":
        return LocalRevisionClient()

    api_key = _get_env("ANTHROPIC_API_KEY")
    if api_key:
        return AnthropicRevisionClient(
            api_key=api_key,
            model=_get_env("ANTHROPIC_MODEL") or DEFAULT_ANTHROPIC_MODEL,
        )

    return MisconfiguredRevisionClient()


def get_feedback_store() -> FeedbackStore:
    return _feedback_store


def build_llm_revision_payload(request: FeedbackRevisionRequest) -> LLMRevisionPayload:
    response_format = {
        "type": "json_schema",
        "json_schema": {
            "name": "resume_targeted_revision",
            "schema": {
                "type": "object",
                "additionalProperties": False,
                "required": ["proposedRevision", "rationale"],
                "properties": {
                    "proposedRevision": {
                        "type": "string",
                        "description": "Replacement text for the selected line range only.",
                    },
                    "rationale": {
                        "type": "string",
                        "description": (
                            "One concise sentence explaining why the revision fits the feedback."
                        ),
                    },
                },
            },
        },
    }
    user_content = "\n".join(
        [
            "Targeted resume revision request",
            f"Request id: {request.id}",
            f"Base version: {request.base_version_id}",
            f"Current generated version: {request.compare_version_id}",
            f"Target version to edit: {request.target_version_id}",
            f"Line range: {request.line_start}-{request.line_end}",
            "",
            "Current generated text selected by user:",
            _fenced(request.selected_text),
            "",
            "User feedback for this selected text:",
            _fenced(request.instruction),
            "",
            "Base/original snapshot for comparison:",
            _fenced(request.base_snapshot),
            "",
            "Current generated resume snapshot:",
            _fenced(request.compare_snapshot),
            "",
            "Return only a replacement for the selected text. Do not rewrite unrelated lines.",
        ],
    )

    return LLMRevisionPayload(
        responseFormat=response_format,
        messages=[
            LLMMessage(
                role="system",
                content=(
                    "You revise resume text. Produce targeted replacements only for the "
                    "selected generated text and preserve unrelated resume content."
                ),
            ),
            LLMMessage(role="user", content=user_content),
        ],
    )


router = APIRouter(prefix="/api/resume/review-feedback", tags=["resume-feedback"])


@router.post("/revision", response_model=FeedbackRevisionResponse)
async def create_feedback_revision(
    request: FeedbackRevisionRequest,
    client: Annotated[ResumeRevisionClient, Depends(get_revision_client)],
    store: Annotated[FeedbackStore, Depends(get_feedback_store)],
) -> FeedbackRevisionResponse:
    payload = build_llm_revision_payload(request)
    try:
        revision = await client.propose_revision(request, payload)
    except MissingRevisionClientConfig as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except RevisionClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    response = FeedbackRevisionResponse(
        requestId=request.id,
        targetVersionId=request.target_version_id,
        lineStart=request.line_start,
        lineEnd=request.line_end,
        proposedRevision=revision.proposed_revision,
        rationale=revision.rationale,
        llmPayload=payload,
    )
    await store.save(request, response)
    return response


@router.get("/threads", response_model=list[FeedbackThreadRecord])
async def list_feedback_threads(
    store: Annotated[FeedbackStore, Depends(get_feedback_store)],
    target_version_id: Annotated[
        str | None,
        Query(alias="targetVersionId"),
    ] = None,
) -> list[FeedbackThreadRecord]:
    return await store.list(target_version_id=target_version_id)


@router.patch("/threads/{request_id}", response_model=FeedbackThreadRecord)
async def update_feedback_thread(
    request_id: str,
    update: FeedbackThreadUpdate,
    store: Annotated[FeedbackStore, Depends(get_feedback_store)],
) -> FeedbackThreadRecord:
    record = await store.update(request_id, update)
    if record is None:
        raise HTTPException(status_code=404, detail="Feedback thread not found")

    return record


def _fallback_revision(request: FeedbackRevisionRequest) -> str:
    text = request.selected_text.strip()
    instruction = request.instruction.strip()

    if re.match(r"^(remove|delete|drop)\b", instruction, flags=re.IGNORECASE):
        return ""

    if re.search(r"revenue|metric|specific|impact|quant", instruction, re.IGNORECASE):
        return (
            f"{text.rstrip('.')}, with measurable impact across revenue-team adoption, "
            "pipeline influence, and sales readiness."
        )

    if re.search(r"punch|strong|sharper|confident|active", instruction, re.IGNORECASE):
        candidate = re.sub(
            r"^Product marketer|^Product marketing manager",
            "Product marketing leader",
            text,
            flags=re.IGNORECASE,
        )
        if _normalize(candidate) != _normalize(text):
            return candidate

    focus = re.sub(
        r"\b(make|this|it|line|please|more|less)\b",
        "",
        instruction,
        flags=re.IGNORECASE,
    )
    focus = re.sub(r"\s+", " ", focus).strip(" .") or "the user's feedback"
    return f"{text.rstrip('.')}, revised to emphasize {focus}."


def _fenced(value: str) -> str:
    return f"```\n{value}\n```"


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().lower()


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _get_env(name: str) -> str | None:
    value = os.getenv(name)
    if value:
        return value

    for env_file in _env_files():
        parsed_value = _read_env_file_value(env_file, name)
        if parsed_value:
            return parsed_value

    return None


def _env_files() -> list[Path]:
    api_dir = Path(__file__).resolve().parent
    root_dir = api_dir.parents[1]

    return [
        api_dir / ".env.local",
        api_dir / ".env",
        root_dir / ".env.local",
        root_dir / ".env",
    ]


def _read_env_file_value(path: Path, name: str) -> str | None:
    if not path.exists():
        return None

    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None

    prefix = f"{name}="
    export_prefix = f"export {name}="

    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        value: str | None = None
        if line.startswith(prefix):
            value = line[len(prefix) :]
        elif line.startswith(export_prefix):
            value = line[len(export_prefix) :]

        if value is not None:
            return value.strip().strip("\"'")

    return None


def _extract_anthropic_tool_input(
    message: dict[str, Any],
    tool_name: str,
) -> dict[str, Any]:
    for block in message["content"]:
        if block.get("type") == "tool_use" and block.get("name") == tool_name:
            tool_input = block["input"]
            if isinstance(tool_input, dict):
                return tool_input

    raise KeyError(tool_name)
