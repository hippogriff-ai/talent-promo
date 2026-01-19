"""Virtual filesystem middleware with Linux-like commands.

Provides Linux-like file operations for LLM access to working files:
- ls, read, write, rm, grep, glob, edit

All storage is in-memory and scoped to the session/thread.
User memory/preferences are handled by frontend localStorage.
"""

import json
import logging
import os
import re
from datetime import datetime, timezone
from fnmatch import fnmatch
from typing import Any, Literal, Optional

from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Token threshold for eviction (deepagents: 20,000 tokens ≈ 80KB at 4 chars/token)
TOOL_TOKEN_LIMIT_BEFORE_EVICT = 20000
CHARS_PER_TOKEN = 4
MAX_LINE_LENGTH = 2000
DEFAULT_READ_LIMIT = 500

# Message template for evicted tool results
TOO_LARGE_TOOL_MSG = """Tool result too large, saved at: {file_path}
You can read the result using read_file with offset and limit parameters.
Here are the first 10 lines:
{content_sample}
"""


class FileInfo(BaseModel):
    """File metadata."""
    path: str
    is_dir: bool = False
    size: int = 0
    modified_at: str = ""


class FileData(BaseModel):
    """File content with metadata."""
    content: list[str]  # Lines
    created_at: str
    modified_at: str


class VirtualFilesystem:
    """Virtual filesystem with Linux-like commands.

    All files are stored in-memory and scoped to the session.
    Paths are absolute starting with /.
    """

    def __init__(
        self,
        thread_id: Optional[str] = None,
    ):
        """Initialize virtual filesystem.

        Args:
            thread_id: Thread ID for session-scoped files
        """
        self.thread_id = thread_id

        # In-memory state for all files (keyed by path)
        self._state_files: dict[str, FileData] = {}

    # ==================== Path Validation ====================

    def _validate_path(self, path: str) -> str:
        """Validate and normalize file path.

        Args:
            path: Path to validate

        Returns:
            Normalized path starting with /

        Raises:
            ValueError: If path contains traversal sequences
        """
        if ".." in path or path.startswith("~"):
            raise ValueError(f"Path traversal not allowed: {path}")

        # Reject Windows paths
        if re.match(r"^[a-zA-Z]:", path):
            raise ValueError(f"Windows paths not supported: {path}")

        # Normalize
        normalized = os.path.normpath(path).replace("\\", "/")
        if not normalized.startswith("/"):
            normalized = f"/{normalized}"

        return normalized

    # ==================== Core Operations ====================

    def ls(self, path: str = "/") -> list[FileInfo]:
        """List files and directories in path.

        Args:
            path: Directory path (default: root)

        Returns:
            List of FileInfo objects
        """
        path = self._validate_path(path)
        normalized = path if path.endswith("/") else path + "/"

        infos: list[FileInfo] = []
        subdirs: set[str] = set()

        # List state files
        for file_path, fd in self._state_files.items():
            if normalized != "/" and not file_path.startswith(normalized):
                continue

            relative = file_path[len(normalized):] if normalized != "/" else file_path[1:]

            if "/" in relative:
                subdir = relative.split("/")[0]
                subdirs.add(f"{normalized}{subdir}/")
            else:
                infos.append(FileInfo(
                    path=file_path,
                    is_dir=False,
                    size=len("\n".join(fd.content)),
                    modified_at=fd.modified_at,
                ))

        # Add directories
        for subdir in sorted(subdirs):
            infos.append(FileInfo(path=subdir, is_dir=True))

        return sorted(infos, key=lambda x: x.path)

    def read(
        self,
        file_path: str,
        offset: int = 0,
        limit: int = DEFAULT_READ_LIMIT,
    ) -> str:
        """Read file content with line numbers.

        Args:
            file_path: Absolute file path
            offset: Line offset (0-indexed)
            limit: Max lines to read

        Returns:
            Formatted content with line numbers, or error message
        """
        file_path = self._validate_path(file_path)

        fd = self._state_files.get(file_path)
        if not fd:
            return f"Error: File '{file_path}' not found"

        return self._format_content(fd.content, offset, limit)

    def _format_content(self, lines: list[str], offset: int, limit: int) -> str:
        """Format content with line numbers (cat -n style)."""
        # Check for empty content
        if not lines or (len(lines) == 1 and not lines[0].strip()):
            return "System reminder: File exists but has empty contents"

        # Apply pagination
        end = offset + limit
        paginated = lines[offset:end]

        # Format with line numbers
        result_lines = []
        for i, line in enumerate(paginated):
            line_num = offset + i + 1
            truncated = line[:MAX_LINE_LENGTH] + "..." if len(line) > MAX_LINE_LENGTH else line
            result_lines.append(f"{line_num:6}\t{truncated}")

        return "\n".join(result_lines)

    def write(self, file_path: str, content: str) -> dict[str, Any]:
        """Write content to a file.

        Args:
            file_path: Absolute file path
            content: File content

        Returns:
            Result dict with path or error
        """
        file_path = self._validate_path(file_path)

        # Check if exists
        if file_path in self._state_files:
            return {"error": f"File '{file_path}' already exists. Use edit or rm first."}

        # Create file
        now = datetime.now(timezone.utc).isoformat()
        self._state_files[file_path] = FileData(
            content=content.split("\n"),
            created_at=now,
            modified_at=now,
        )

        return {"path": file_path}

    def edit(
        self,
        file_path: str,
        old_string: str,
        new_string: str,
        replace_all: bool = False,
    ) -> dict[str, Any]:
        """Edit file by replacing string.

        Args:
            file_path: File to edit
            old_string: String to find
            new_string: Replacement string
            replace_all: Replace all occurrences

        Returns:
            Result dict with path/occurrences or error
        """
        file_path = self._validate_path(file_path)

        fd = self._state_files.get(file_path)
        if not fd:
            return {"error": f"File '{file_path}' not found"}

        content = "\n".join(fd.content)
        count = content.count(old_string)

        if count == 0:
            return {"error": f"String not found in {file_path}"}
        if count > 1 and not replace_all:
            return {"error": f"Found {count} occurrences. Use replace_all=True or provide more context."}

        new_content = content.replace(old_string, new_string) if replace_all else content.replace(old_string, new_string, 1)

        fd.content = new_content.split("\n")
        fd.modified_at = datetime.now(timezone.utc).isoformat()

        return {"path": file_path, "occurrences": count if replace_all else 1}

    def rm(self, file_path: str) -> dict[str, Any]:
        """Remove a file.

        Args:
            file_path: File to remove

        Returns:
            Result dict with path or error
        """
        file_path = self._validate_path(file_path)

        if file_path not in self._state_files:
            return {"error": f"File '{file_path}' not found"}

        del self._state_files[file_path]
        return {"path": file_path}

    def grep(
        self,
        pattern: str,
        path: str = "/",
        glob_pattern: Optional[str] = None,
        output_mode: Literal["files_with_matches", "content", "count"] = "files_with_matches",
    ) -> str:
        """Search for pattern in files.

        Args:
            pattern: Text pattern to search (literal string)
            path: Directory to search in
            glob_pattern: File pattern filter (e.g., "*.json")
            output_mode: Output format

        Returns:
            Search results formatted per output_mode
        """
        path = self._validate_path(path)
        matches: list[dict[str, Any]] = []

        # Search state files
        for file_path, fd in self._state_files.items():
            if not file_path.startswith(path):
                continue
            if glob_pattern and not fnmatch(file_path, glob_pattern):
                continue

            content = "\n".join(fd.content)
            if pattern in content:
                for i, line in enumerate(fd.content):
                    if pattern in line:
                        matches.append({
                            "path": file_path,
                            "line": i + 1,
                            "text": line[:200],
                        })

        if not matches:
            return "No matches found"

        if output_mode == "files_with_matches":
            paths = sorted(set(m["path"] for m in matches))
            return "\n".join(paths)
        elif output_mode == "count":
            counts: dict[str, int] = {}
            for m in matches:
                counts[m["path"]] = counts.get(m["path"], 0) + 1
            return "\n".join(f"{p}: {c}" for p, c in sorted(counts.items()))
        else:  # content
            lines = []
            for m in matches:
                lines.append(f"{m['path']}:{m['line']}:{m['text']}")
            return "\n".join(lines)

    def glob(self, pattern: str, path: str = "/") -> list[str]:
        """Find files matching glob pattern.

        Args:
            pattern: Glob pattern (e.g., "**/*.json")
            path: Base path to search from

        Returns:
            List of matching file paths
        """
        path = self._validate_path(path)
        matches: list[str] = []

        # Check state files
        for file_path in self._state_files:
            if not file_path.startswith(path):
                continue
            if fnmatch(file_path, pattern) or fnmatch(file_path, f"{path}/{pattern}"):
                matches.append(file_path)

        return sorted(matches)

    # ==================== Large Tool Result Offloading ====================

    def offload_if_large(self, tool_call_id: str, content: str) -> tuple[str, bool]:
        """Offload large tool result to filesystem.

        Following deepagents pattern: if content > 20K tokens, write to
        /large_tool_results/{tool_call_id} and return truncated preview.

        Args:
            tool_call_id: Tool call ID for filename
            content: Tool result content

        Returns:
            Tuple of (processed_content, was_offloaded)
        """
        # Check size threshold
        if len(content) <= TOOL_TOKEN_LIMIT_BEFORE_EVICT * CHARS_PER_TOKEN:
            return content, False

        # Sanitize tool_call_id for filename
        sanitized_id = re.sub(r"[^a-zA-Z0-9_-]", "_", tool_call_id)
        file_path = f"/large_tool_results/{sanitized_id}"

        # Write to filesystem
        result = self.write(file_path, content)
        if "error" in result:
            # If write fails, return original (truncated)
            logger.warning(f"Failed to offload: {result['error']}")
            return content[:TOOL_TOKEN_LIMIT_BEFORE_EVICT * CHARS_PER_TOKEN] + "\n[truncated]", False

        # Create truncated preview
        lines = content.split("\n")[:10]
        preview = self._format_content(lines, 0, 10)

        replacement = TOO_LARGE_TOOL_MSG.format(
            file_path=file_path,
            content_sample=preview,
        )

        return replacement, True

    def get_offloaded_result(self, tool_call_id: str, offset: int = 0, limit: int = 500) -> str:
        """Retrieve an offloaded tool result.

        Args:
            tool_call_id: Original tool call ID
            offset: Line offset for pagination
            limit: Max lines to read

        Returns:
            File content with line numbers
        """
        sanitized_id = re.sub(r"[^a-zA-Z0-9_-]", "_", tool_call_id)
        file_path = f"/large_tool_results/{sanitized_id}"
        return self.read(file_path, offset, limit)

    # ==================== State Management ====================

    def get_state(self) -> dict[str, Any]:
        """Export state for checkpointing."""
        return {
            "files": {
                path: {
                    "content": fd.content,
                    "created_at": fd.created_at,
                    "modified_at": fd.modified_at,
                }
                for path, fd in self._state_files.items()
            },
            "thread_id": self.thread_id,
        }

    def restore_state(self, state: dict[str, Any]) -> None:
        """Restore state from checkpoint."""
        self._state_files.clear()

        files = state.get("files", {})
        for path, data in files.items():
            self._state_files[path] = FileData(
                content=data["content"],
                created_at=data["created_at"],
                modified_at=data["modified_at"],
            )

        if state.get("thread_id"):
            self.thread_id = state["thread_id"]


# ==================== Singleton ====================

_vfs: Optional[VirtualFilesystem] = None


def get_vfs(
    thread_id: Optional[str] = None,
    **kwargs,  # Accept but ignore user_id for backwards compatibility
) -> VirtualFilesystem:
    """Get or create VirtualFilesystem instance.

    Args:
        thread_id: Thread ID for session scope

    Returns:
        VirtualFilesystem instance
    """
    global _vfs

    # Create new if params change
    if _vfs is None or _vfs.thread_id != thread_id:
        _vfs = VirtualFilesystem(thread_id=thread_id)

    return _vfs


def reset_vfs() -> None:
    """Reset singleton (for testing)."""
    global _vfs
    _vfs = None
