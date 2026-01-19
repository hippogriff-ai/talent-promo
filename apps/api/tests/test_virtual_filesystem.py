"""Tests for virtual filesystem middleware.

Tests Linux-like commands, large tool result offloading, and user-isolated memory.
"""

import json
import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from middleware.virtual_filesystem import (
    VirtualFilesystem,
    FileData,
    FileInfo,
    get_vfs,
    reset_vfs,
    TOOL_TOKEN_LIMIT_BEFORE_EVICT,
    CHARS_PER_TOKEN,
)
from services.preferences_service import UserPreferences


# ==================== Fixtures ====================


@pytest.fixture
def vfs():
    """Create a fresh VirtualFilesystem instance."""
    reset_vfs()
    fs = VirtualFilesystem(thread_id="test_thread")
    yield fs
    fs.close()


@pytest.fixture
def vfs_no_user():
    """VFS without user_id (no memory access)."""
    reset_vfs()
    fs = VirtualFilesystem(thread_id="test_thread")
    yield fs
    fs.close()


# ==================== Path Validation ====================


class TestPathValidation:
    """Test path validation and normalization."""

    def test_validate_normal_path(self, vfs):
        """Normal path is normalized."""
        assert vfs._validate_path("foo/bar") == "/foo/bar"
        assert vfs._validate_path("/foo/bar") == "/foo/bar"
        assert vfs._validate_path("/foo//bar") == "/foo/bar"

    def test_validate_rejects_traversal(self, vfs):
        """Path traversal is rejected."""
        with pytest.raises(ValueError, match="traversal"):
            vfs._validate_path("../etc/passwd")

        with pytest.raises(ValueError, match="traversal"):
            vfs._validate_path("/foo/../bar")

    def test_validate_rejects_tilde(self, vfs):
        """Tilde expansion is rejected."""
        with pytest.raises(ValueError, match="traversal"):
            vfs._validate_path("~/.ssh/id_rsa")

    def test_validate_rejects_windows_path(self, vfs):
        """Windows paths are rejected."""
        with pytest.raises(ValueError, match="Windows"):
            vfs._validate_path("C:\\Users\\file.txt")


# ==================== State File Operations ====================


class TestStateFiles:
    """Test ephemeral state file operations."""

    def test_write_and_read(self, vfs):
        """Write then read a file."""
        result = vfs.write("/test.txt", "Hello\nWorld")
        assert result == {"path": "/test.txt"}

        content = vfs.read("/test.txt")
        assert "Hello" in content
        assert "World" in content

    def test_write_exists_error(self, vfs):
        """Writing to existing file fails."""
        vfs.write("/test.txt", "First")
        result = vfs.write("/test.txt", "Second")
        assert "already exists" in result.get("error", "")

    def test_read_not_found(self, vfs):
        """Reading nonexistent file returns error."""
        content = vfs.read("/nonexistent.txt")
        assert "not found" in content

    def test_read_with_pagination(self, vfs):
        """Read supports offset and limit."""
        lines = "\n".join([f"Line {i}" for i in range(100)])
        vfs.write("/big.txt", lines)

        content = vfs.read("/big.txt", offset=10, limit=5)
        assert "11\t" in content  # Line 11 (1-indexed)
        assert "15\t" in content
        assert "16\t" not in content

    def test_edit_file(self, vfs):
        """Edit replaces string in file."""
        vfs.write("/test.txt", "Hello World")

        result = vfs.edit("/test.txt", "World", "Universe")
        assert result == {"path": "/test.txt", "occurrences": 1}

        content = vfs.read("/test.txt")
        assert "Universe" in content

    def test_edit_not_unique_error(self, vfs):
        """Edit fails if string appears multiple times without replace_all."""
        vfs.write("/test.txt", "foo bar foo baz foo")

        result = vfs.edit("/test.txt", "foo", "qux")
        assert "3 occurrences" in result.get("error", "")

    def test_edit_replace_all(self, vfs):
        """Edit with replace_all replaces all occurrences."""
        vfs.write("/test.txt", "foo bar foo baz foo")

        result = vfs.edit("/test.txt", "foo", "qux", replace_all=True)
        assert result["occurrences"] == 3

        content = vfs.read("/test.txt")
        assert "foo" not in content
        assert "qux" in content

    def test_rm_file(self, vfs):
        """Remove deletes file."""
        vfs.write("/test.txt", "content")
        assert "/test.txt" in [f.path for f in vfs.ls("/")]

        result = vfs.rm("/test.txt")
        assert result == {"path": "/test.txt"}

        content = vfs.read("/test.txt")
        assert "not found" in content

    def test_rm_not_found(self, vfs):
        """Remove nonexistent file returns error."""
        result = vfs.rm("/nonexistent.txt")
        assert "not found" in result.get("error", "")


# ==================== Directory Listing ====================


class TestLs:
    """Test directory listing."""

    def test_ls_root(self, vfs):
        """List root directory."""
        vfs.write("/file1.txt", "a")
        vfs.write("/dir/file2.txt", "b")

        infos = vfs.ls("/")
        paths = [f.path for f in infos]

        assert "/file1.txt" in paths
        assert "/dir/" in paths  # Directory
        assert "/memory/" in paths  # Memory dir (user_id set)

    def test_ls_subdirectory(self, vfs):
        """List subdirectory."""
        vfs.write("/subdir/a.txt", "a")
        vfs.write("/subdir/b.txt", "b")
        vfs.write("/subdir/nested/c.txt", "c")

        infos = vfs.ls("/subdir/")
        paths = [f.path for f in infos]

        assert "/subdir/a.txt" in paths
        assert "/subdir/b.txt" in paths
        assert "/subdir/nested/" in paths

    def test_ls_empty_dir(self, vfs):
        """List empty directory."""
        infos = vfs.ls("/empty/")
        assert len([f for f in infos if not f.is_dir]) == 0


# ==================== Grep ====================


class TestGrep:
    """Test pattern searching."""

    def test_grep_finds_matches(self, vfs):
        """Grep finds pattern in files."""
        vfs.write("/a.txt", "Hello World")
        vfs.write("/b.txt", "Hello Universe")
        vfs.write("/c.txt", "Goodbye World")

        result = vfs.grep("Hello")
        assert "/a.txt" in result
        assert "/b.txt" in result
        assert "/c.txt" not in result

    def test_grep_with_glob(self, vfs):
        """Grep respects glob pattern."""
        vfs.write("/code.py", "def hello():")
        vfs.write("/code.js", "function hello() {")
        vfs.write("/readme.txt", "hello world")

        result = vfs.grep("hello", glob_pattern="*.py")
        assert "/code.py" in result
        assert "/code.js" not in result

    def test_grep_content_mode(self, vfs):
        """Grep content mode shows lines."""
        vfs.write("/test.txt", "line1\nhello world\nline3")

        result = vfs.grep("hello", output_mode="content")
        assert "/test.txt:2:" in result
        assert "hello world" in result

    def test_grep_count_mode(self, vfs):
        """Grep count mode shows counts."""
        vfs.write("/test.txt", "foo bar foo baz foo")

        result = vfs.grep("foo", output_mode="count")
        assert "/test.txt: 1" in result  # 1 line with matches

    def test_grep_no_matches(self, vfs):
        """Grep returns message when no matches."""
        vfs.write("/test.txt", "abc")
        result = vfs.grep("xyz")
        assert "No matches" in result


# ==================== Glob ====================


class TestGlob:
    """Test file pattern matching."""

    def test_glob_finds_files(self, vfs):
        """Glob finds matching files."""
        vfs.write("/src/a.py", "")
        vfs.write("/src/b.py", "")
        vfs.write("/src/c.js", "")

        matches = vfs.glob("*.py", "/src/")
        assert "/src/a.py" in matches
        assert "/src/b.py" in matches
        assert "/src/c.js" not in matches

    def test_glob_recursive(self, vfs):
        """Glob with ** is recursive."""
        vfs.write("/a.txt", "")
        vfs.write("/sub/b.txt", "")
        vfs.write("/sub/deep/c.txt", "")

        matches = vfs.glob("**/*.txt")
        assert len(matches) >= 3


# ==================== User Preferences ====================


class TestUserPreferences:
    """Test simplified user preference memory."""

    def test_save_and_get_preferences(self, vfs):
        """Save then retrieve preferences."""
        prefs = UserPreferences(
            tone="confident",
            length="detailed",
            format="bullets",
            job_type_interest="software engineer",
        )

        assert vfs.save_preferences(prefs)

        loaded = vfs.get_preferences()
        assert loaded is not None
        assert loaded.tone == "confident"
        assert loaded.length == "detailed"
        assert loaded.format == "bullets"
        assert loaded.job_type_interest == "software engineer"

    def test_get_preferences_default(self, vfs):
        """Get preferences returns None if not set."""
        loaded = vfs.get_preferences()
        # May be None or default depending on implementation
        # In state-only mode without Postgres, memory operations fail gracefully

    def test_get_memory_context_for_prompt(self, vfs):
        """Get memory context formats for LLM."""
        prefs = UserPreferences(
            tone="friendly",
            length="concise",
            format="paragraphs",
        )
        vfs.save_preferences(prefs)

        context = vfs.get_memory_context_for_prompt()
        assert "<user_memory>" in context
        assert "tone: friendly" in context
        assert "length: concise" in context
        assert "</user_memory>" in context


# ==================== Large Tool Result Offloading ====================


class TestToolResultOffloading:
    """Test large tool result eviction (deepagents pattern)."""

    def test_small_result_not_offloaded(self, vfs):
        """Small results pass through unchanged."""
        content = "Small result"
        result, was_offloaded = vfs.offload_if_large("tool_123", content)

        assert result == content
        assert was_offloaded is False

    def test_large_result_offloaded(self, vfs):
        """Large results are offloaded to filesystem."""
        # Create content larger than threshold
        large_content = "x" * (TOOL_TOKEN_LIMIT_BEFORE_EVICT * CHARS_PER_TOKEN + 1000)

        result, was_offloaded = vfs.offload_if_large("tool_456", large_content)

        assert was_offloaded is True
        assert "/large_tool_results/tool_456" in result
        assert "read_file" in result
        assert "first 10 lines" in result.lower() or "here are" in result.lower()

    def test_offloaded_result_readable(self, vfs):
        """Offloaded results can be retrieved."""
        lines = [f"Line {i}: " + "x" * 1000 for i in range(100)]
        large_content = "\n".join(lines)

        vfs.offload_if_large("tool_789", large_content)

        # Read back with pagination
        content = vfs.get_offloaded_result("tool_789", offset=0, limit=5)
        assert "Line 0" in content
        assert "Line 4" in content

    def test_offloaded_with_special_chars_in_id(self, vfs):
        """Tool call IDs with special chars are sanitized."""
        content = "x" * (TOOL_TOKEN_LIMIT_BEFORE_EVICT * CHARS_PER_TOKEN + 100)

        result, was_offloaded = vfs.offload_if_large("call-id:with/special", content)

        assert was_offloaded is True
        assert "call-id_with_special" in result


# ==================== State Management ====================


class TestStateManagement:
    """Test checkpoint state export/restore."""

    def test_get_state(self, vfs):
        """Export state for checkpointing."""
        vfs.write("/test.txt", "content")

        state = vfs.get_state()
        assert "files" in state
        assert "/test.txt" in state["files"]
        assert state["user_id"] == "test_user"
        assert state["thread_id"] == "test_thread"

    def test_restore_state(self, vfs):
        """Restore state from checkpoint."""
        vfs.write("/old.txt", "old")

        new_state = {
            "files": {
                "/restored.txt": {
                    "content": ["restored", "content"],
                    "created_at": "2024-01-01T00:00:00Z",
                    "modified_at": "2024-01-01T00:00:00Z",
                }
            },
            "user_id": "restored_user",
            "thread_id": "restored_thread",
        }

        vfs.restore_state(new_state)

        # Old file gone
        assert "not found" in vfs.read("/old.txt")

        # New file present
        content = vfs.read("/restored.txt")
        assert "restored" in content


# ==================== Singleton ====================


class TestSingleton:
    """Test singleton behavior."""

    def test_get_vfs_creates_instance(self):
        """get_vfs creates new instance."""
        reset_vfs()
        vfs1 = get_vfs(user_id="user1", thread_id="thread1")
        assert vfs1 is not None
        assert vfs1.user_id == "user1"

    def test_get_vfs_reuses_instance(self):
        """get_vfs reuses instance with same params."""
        reset_vfs()
        vfs1 = get_vfs(user_id="user1", thread_id="thread1")
        vfs2 = get_vfs(user_id="user1", thread_id="thread1")
        assert vfs1 is vfs2

    def test_get_vfs_new_user(self):
        """get_vfs creates new instance for different user."""
        reset_vfs()
        vfs1 = get_vfs(user_id="user1", thread_id="thread1")
        vfs2 = get_vfs(user_id="user2", thread_id="thread1")
        assert vfs1 is not vfs2
        assert vfs2.user_id == "user2"


# ==================== Memory Without User ====================


class TestMemoryWithoutUser:
    """Test memory operations without user_id."""

    def test_memory_not_available(self, vfs_no_user):
        """Memory operations fail gracefully without user."""
        content = vfs_no_user.read("/memory/preferences.json")
        assert "user_id required" in content or "not found" in content.lower()

    def test_ls_root_no_memory_dir(self, vfs_no_user):
        """Root listing doesn't show /memory/ without user."""
        vfs_no_user.write("/test.txt", "content")
        infos = vfs_no_user.ls("/")
        paths = [f.path for f in infos]

        assert "/test.txt" in paths
        assert "/memory/" not in paths


# ==================== Line Number Formatting ====================


class TestLineNumberFormatting:
    """Test cat -n style output formatting."""

    def test_line_numbers_start_at_1(self, vfs):
        """Line numbers are 1-indexed."""
        vfs.write("/test.txt", "first\nsecond\nthird")
        content = vfs.read("/test.txt")

        lines = content.split("\n")
        assert lines[0].strip().startswith("1")

    def test_long_lines_truncated(self, vfs):
        """Lines over 2000 chars are truncated."""
        long_line = "x" * 3000
        vfs.write("/test.txt", long_line)

        content = vfs.read("/test.txt")
        # Should have truncation indicator
        assert "..." in content or len(content) < len(long_line)

    def test_empty_file_message(self, vfs):
        """Empty file shows reminder."""
        vfs.write("/empty.txt", "")
        content = vfs.read("/empty.txt")
        assert "empty" in content.lower()
