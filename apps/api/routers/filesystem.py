"""API router for virtual filesystem operations.

Exposes Linux-like commands: ls, read, write, edit, rm, grep, glob
for LLM access to working files during a session.
"""

import logging
from typing import Any, Literal, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from middleware.virtual_filesystem import (
    VirtualFilesystem,
    FileInfo,
    get_vfs,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/fs", tags=["filesystem"])


# ==================== Request/Response Models ====================


class WriteRequest(BaseModel):
    """Request to write a file."""
    file_path: str = Field(..., description="Absolute file path starting with /")
    content: str = Field(..., description="File content to write")


class EditRequest(BaseModel):
    """Request to edit a file."""
    file_path: str = Field(..., description="Absolute file path starting with /")
    old_string: str = Field(..., description="String to find")
    new_string: str = Field(..., description="Replacement string")
    replace_all: bool = Field(False, description="Replace all occurrences")


class GrepRequest(BaseModel):
    """Request to search files."""
    pattern: str = Field(..., description="Pattern to search for")
    path: str = Field("/", description="Directory to search in")
    glob_pattern: Optional[str] = Field(None, description="File pattern filter")
    output_mode: Literal["files_with_matches", "content", "count"] = Field(
        "files_with_matches", description="Output format"
    )


class OperationResult(BaseModel):
    """Generic operation result."""
    success: bool
    path: Optional[str] = None
    error: Optional[str] = None
    occurrences: Optional[int] = None


# ==================== Helper ====================


def _get_vfs(thread_id: Optional[str]) -> VirtualFilesystem:
    """Get VFS instance with optional thread context."""
    return get_vfs(thread_id=thread_id)


# ==================== Endpoints ====================


@router.get("/ls")
async def list_files(
    path: str = Query("/", description="Directory path to list"),
    thread_id: Optional[str] = Query(None, description="Thread ID for session scope"),
) -> list[dict[str, Any]]:
    """List files and directories in path.

    Linux equivalent: ls -la <path>

    Returns list of FileInfo objects with path, is_dir, size, modified_at.
    """
    vfs = _get_vfs(thread_id)
    infos = vfs.ls(path)
    return [info.model_dump() for info in infos]


@router.get("/read")
async def read_file(
    file_path: str = Query(..., description="Absolute file path"),
    offset: int = Query(0, description="Line offset (0-indexed)"),
    limit: int = Query(500, description="Max lines to read"),
    thread_id: Optional[str] = Query(None, description="Thread ID for session scope"),
) -> dict[str, Any]:
    """Read file content with line numbers.

    Linux equivalent: cat -n <file> | head -n <limit> | tail -n +<offset>

    Returns content with line numbers (1-indexed, cat -n style).
    For large files, use offset/limit for pagination.
    """
    vfs = _get_vfs(thread_id)
    content = vfs.read(file_path, offset=offset, limit=limit)

    if content.startswith("Error:"):
        raise HTTPException(status_code=404, detail=content)

    return {
        "path": file_path,
        "content": content,
        "offset": offset,
        "limit": limit,
    }


@router.post("/write")
async def write_file(
    request: WriteRequest,
    thread_id: Optional[str] = Query(None, description="Thread ID for session scope"),
) -> OperationResult:
    """Write content to a new file.

    Linux equivalent: echo "content" > <file_path>

    Fails if file already exists. Use edit to modify existing files.
    """
    vfs = _get_vfs(thread_id)
    result = vfs.write(request.file_path, request.content)

    if "error" in result:
        return OperationResult(success=False, error=result["error"])

    return OperationResult(success=True, path=result["path"])


@router.post("/edit")
async def edit_file(
    request: EditRequest,
    thread_id: Optional[str] = Query(None, description="Thread ID for session scope"),
) -> OperationResult:
    """Edit file by replacing string.

    Linux equivalent: sed -i 's/old/new/' <file_path>

    If old_string appears multiple times, fails unless replace_all=True.
    """
    vfs = _get_vfs(thread_id)
    result = vfs.edit(
        request.file_path,
        request.old_string,
        request.new_string,
        replace_all=request.replace_all,
    )

    if "error" in result:
        return OperationResult(success=False, error=result["error"])

    return OperationResult(
        success=True,
        path=result["path"],
        occurrences=result.get("occurrences"),
    )


@router.delete("/rm")
async def remove_file(
    file_path: str = Query(..., description="File to remove"),
    thread_id: Optional[str] = Query(None, description="Thread ID for session scope"),
) -> OperationResult:
    """Remove a file.

    Linux equivalent: rm <file_path>

    Cannot remove directories (yet).
    """
    vfs = _get_vfs(thread_id)
    result = vfs.rm(file_path)

    if "error" in result:
        return OperationResult(success=False, error=result["error"])

    return OperationResult(success=True, path=result["path"])


@router.post("/grep")
async def search_files(
    request: GrepRequest,
    thread_id: Optional[str] = Query(None, description="Thread ID for session scope"),
) -> dict[str, Any]:
    """Search for pattern in files.

    Linux equivalent: grep -r "pattern" <path>

    output_mode options:
    - files_with_matches: List matching file paths (default)
    - content: Show matching lines with file:line:text
    - count: Show match counts per file
    """
    vfs = _get_vfs(thread_id)
    result = vfs.grep(
        request.pattern,
        path=request.path,
        glob_pattern=request.glob_pattern,
        output_mode=request.output_mode,
    )

    return {
        "pattern": request.pattern,
        "path": request.path,
        "output_mode": request.output_mode,
        "result": result,
    }


@router.get("/glob")
async def find_files(
    pattern: str = Query(..., description="Glob pattern (e.g., **/*.json)"),
    path: str = Query("/", description="Base path to search from"),
    thread_id: Optional[str] = Query(None, description="Thread ID for session scope"),
) -> list[str]:
    """Find files matching glob pattern.

    Linux equivalent: find <path> -name "pattern"

    Supports standard glob patterns: * (any chars), ** (recursive), ? (single char)
    """
    vfs = _get_vfs(thread_id)
    return vfs.glob(pattern, path)


# ==================== Tool Result Offloading ====================


@router.post("/offload")
async def offload_tool_result(
    tool_call_id: str = Query(..., description="Tool call ID"),
    content: str = Query(..., description="Tool result content"),
    thread_id: Optional[str] = Query(None, description="Thread ID"),
) -> dict[str, Any]:
    """Offload large tool result to filesystem.

    If content exceeds 20K tokens (~80KB), saves to /large_tool_results/{id}
    and returns truncated preview with file reference.

    Returns:
    - processed_content: Original or truncated content with file reference
    - was_offloaded: True if content was offloaded
    """
    vfs = _get_vfs(thread_id)
    processed, was_offloaded = vfs.offload_if_large(tool_call_id, content)

    return {
        "processed_content": processed,
        "was_offloaded": was_offloaded,
    }


@router.get("/offloaded/{tool_call_id}")
async def get_offloaded_result(
    tool_call_id: str,
    offset: int = Query(0, description="Line offset"),
    limit: int = Query(500, description="Max lines"),
    thread_id: Optional[str] = Query(None, description="Thread ID"),
) -> dict[str, Any]:
    """Retrieve an offloaded tool result.

    Reads from /large_tool_results/{tool_call_id} with pagination support.
    """
    vfs = _get_vfs(thread_id)
    content = vfs.get_offloaded_result(tool_call_id, offset=offset, limit=limit)

    if content.startswith("Error:"):
        raise HTTPException(status_code=404, detail=content)

    return {
        "tool_call_id": tool_call_id,
        "content": content,
        "offset": offset,
        "limit": limit,
    }
