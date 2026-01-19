# Virtual Filesystem Spec

## Overview

A generic virtual filesystem that agents use for **all file operations** - reading memory, writing drafts, storing intermediate results, and managing working files. The same Linux-like interface works across all use cases.

**Key Principles:**
- One unified interface for all file operations
- Agents interact with files the same way regardless of storage backend
- No embeddings - simple string/regex operations
- Different paths can have different persistence (ephemeral vs permanent)

## Use Cases

| Use Case | Path | Persistence | Example |
|----------|------|-------------|---------|
| User memory | `/memory/` | Permanent (cross-session) | `/memory/preferences.md` |
| Working drafts | `/drafts/` | Thread-scoped | `/drafts/resume_v2.html` |
| Intermediate results | `/tmp/` | Ephemeral | `/tmp/parsed_job.json` |
| Research data | `/research/` | Thread-scoped | `/research/company_info.md` |
| Export outputs | `/exports/` | Thread-scoped | `/exports/resume.pdf` |

## Architecture

### Storage Routing

```
Virtual Path          →  Storage Backend
─────────────────────────────────────────
/memory/**            →  PostgresStore (permanent)
/drafts/**            →  StateBackend (thread-scoped)
/tmp/**               →  StateBackend (ephemeral)
/research/**          →  StateBackend (thread-scoped)
/exports/**           →  StateBackend (thread-scoped)
```

### Virtual Filesystem Layout

```
/                                 # Root
├── /memory/                      # Permanent user memory
│   ├── preferences.md            # Tone, style, structure prefs
│   ├── facts.md                  # Learned facts about user
│   └── history.md                # Interaction history summary
│
├── /drafts/                      # Working resume drafts
│   ├── current.html              # Current draft
│   ├── v1.html                   # Version 1
│   ├── v2.html                   # Version 2
│   └── suggestions.json          # Pending suggestions
│
├── /research/                    # Research phase data
│   ├── profile.json              # Parsed user profile
│   ├── job.json                  # Parsed job posting
│   ├── company.md                # Company research
│   └── gap_analysis.json         # Gap analysis results
│
├── /tmp/                         # Temporary working files
│   └── scratch.txt               # Scratch space
│
└── /exports/                     # Export outputs
    ├── resume.pdf                # Generated PDF
    ├── resume.docx               # Generated DOCX
    └── ats_report.json           # ATS analysis
```

## API Design

### Core Operations (Linux-like)

```python
class VirtualFilesystem:
    """Generic virtual filesystem for agent file operations."""

    # === List (ls) ===
    def ls(
        self,
        path: str = "/",
        recursive: bool = False,
        long: bool = False,  # Include metadata
    ) -> list[FileInfo]:
        """List directory contents.

        Examples:
            fs.ls("/")                    # List root
            fs.ls("/drafts/")             # List drafts
            fs.ls("/memory/", long=True)  # With metadata
        """

    # === Read (cat) ===
    def read(
        self,
        path: str,
        offset: int = 0,
        limit: int = 1000,
    ) -> str | None:
        """Read file contents.

        Examples:
            fs.read("/memory/preferences.md")
            fs.read("/drafts/current.html")
            fs.read("/research/job.json")
        """

    # === Write (echo >) ===
    def write(
        self,
        path: str,
        content: str,
        append: bool = False,  # >> vs >
    ) -> WriteResult:
        """Write content to file.

        Examples:
            fs.write("/drafts/v3.html", html_content)
            fs.write("/memory/facts.md", new_fact, append=True)
            fs.write("/tmp/scratch.txt", notes)
        """

    # === Delete (rm) ===
    def rm(self, path: str, recursive: bool = False) -> bool:
        """Delete file or directory.

        Examples:
            fs.rm("/tmp/scratch.txt")
            fs.rm("/drafts/old/", recursive=True)
        """

    # === Search (grep) ===
    def grep(
        self,
        pattern: str,
        path: str = "/",
        ignore_case: bool = False,
        context: int = 0,  # Lines of context (-C)
    ) -> list[GrepMatch]:
        """Search file contents with regex.

        Examples:
            fs.grep("Python", "/memory/")
            fs.grep("error", "/", ignore_case=True)
            fs.grep("TODO", "/drafts/", context=2)
        """

    # === Find (find -name) ===
    def find(
        self,
        pattern: str,  # Glob pattern for filename
        path: str = "/",
        type: str = "any",  # "file" | "dir" | "any"
    ) -> list[str]:
        """Find files by name.

        Examples:
            fs.find("*.html", "/drafts/")
            fs.find("*.json", "/")
            fs.find("preferences*", "/memory/")
        """

    # === Glob ===
    def glob(self, pattern: str) -> list[str]:
        """Match files with glob pattern.

        Examples:
            fs.glob("/drafts/*.html")
            fs.glob("/memory/**/*.md")
            fs.glob("/**/job.json")
        """

    # === Copy (cp) ===
    def cp(self, src: str, dst: str) -> bool:
        """Copy file.

        Examples:
            fs.cp("/drafts/current.html", "/drafts/v3.html")
            fs.cp("/research/job.json", "/tmp/job_backup.json")
        """

    # === Move (mv) ===
    def mv(self, src: str, dst: str) -> bool:
        """Move/rename file.

        Examples:
            fs.mv("/drafts/v3.html", "/drafts/current.html")
            fs.mv("/tmp/output.pdf", "/exports/resume.pdf")
        """

    # === Check existence ===
    def exists(self, path: str) -> bool:
        """Check if path exists."""

    def is_file(self, path: str) -> bool:
        """Check if path is a file."""

    def is_dir(self, path: str) -> bool:
        """Check if path is a directory."""
```

### Data Models

```python
from pydantic import BaseModel
from typing import Literal
from datetime import datetime

class FileInfo(BaseModel):
    """File/directory info from ls."""
    name: str                           # filename.ext or dirname/
    path: str                           # /full/path
    type: Literal["file", "dir"]
    size: int | None = None             # bytes (files only)
    created_at: datetime | None = None
    modified_at: datetime | None = None

class WriteResult(BaseModel):
    """Result of write operation."""
    success: bool
    path: str
    created: bool                       # True if new file
    bytes_written: int

class GrepMatch(BaseModel):
    """Single grep match."""
    path: str
    line_number: int                    # 1-indexed
    line: str                           # Matching line content
    context_before: list[str] = []
    context_after: list[str] = []
```

## Implementation

### File: `apps/api/services/virtual_filesystem.py`

```python
"""Virtual filesystem for agent file operations.

Provides Linux-like file operations (ls, read, write, grep, find, glob)
over multiple storage backends with path-based routing.
"""

import fnmatch
import re
from datetime import datetime, timezone
from typing import Literal, Optional

from pydantic import BaseModel


class FileInfo(BaseModel):
    name: str
    path: str
    type: Literal["file", "dir"]
    size: Optional[int] = None
    created_at: Optional[datetime] = None
    modified_at: Optional[datetime] = None


class WriteResult(BaseModel):
    success: bool
    path: str
    created: bool
    bytes_written: int


class GrepMatch(BaseModel):
    path: str
    line_number: int
    line: str
    context_before: list[str] = []
    context_after: list[str] = []


class VirtualFilesystem:
    """Virtual filesystem with path-based storage routing.

    Routes:
        /memory/** -> Permanent store (PostgresStore)
        /drafts/** -> Thread state
        /research/** -> Thread state
        /tmp/** -> Thread state
        /exports/** -> Thread state
    """

    def __init__(
        self,
        user_id: str,
        thread_id: Optional[str] = None,
        permanent_store=None,
        thread_state: Optional[dict] = None,
    ):
        self.user_id = user_id
        self.thread_id = thread_id
        self._permanent_store = permanent_store
        self._thread_state = thread_state or {}

        # Initialize files dict in thread state if needed
        if "files" not in self._thread_state:
            self._thread_state["files"] = {}

    # === Path Routing ===

    def _is_permanent_path(self, path: str) -> bool:
        """Check if path routes to permanent storage."""
        return path.startswith("/memory/") or path == "/memory"

    def _get_storage(self, path: str):
        """Get appropriate storage for path."""
        if self._is_permanent_path(path):
            return self._get_permanent_store()
        return self._thread_state["files"]

    def _get_permanent_store(self):
        """Get permanent store (lazy init)."""
        if self._permanent_store is None:
            from langgraph.store.memory import InMemoryStore
            self._permanent_store = InMemoryStore()
        return self._permanent_store

    def _normalize_path(self, path: str) -> str:
        """Normalize path to absolute form."""
        if not path:
            path = "/"
        if not path.startswith("/"):
            path = "/" + path
        # Remove double slashes, trailing slash (except root)
        path = re.sub(r"/+", "/", path)
        if path != "/" and path.endswith("/"):
            path = path[:-1]
        return path

    # === List (ls) ===

    def ls(
        self,
        path: str = "/",
        recursive: bool = False,
        long: bool = False,
    ) -> list[FileInfo]:
        """List directory contents."""
        path = self._normalize_path(path)
        results = []
        seen_dirs = set()

        # Get all files from both stores
        all_files = self._get_all_files()

        for file_path, file_data in all_files.items():
            # Check if under requested path
            if path == "/":
                rel = file_path
            elif file_path.startswith(path + "/"):
                rel = file_path[len(path) + 1:]
            elif file_path == path:
                # Exact file match
                results.append(self._file_info(file_path, file_data))
                continue
            else:
                continue

            if not recursive and "/" in rel:
                # Show directory instead
                dir_name = rel.split("/")[0]
                if dir_name not in seen_dirs:
                    seen_dirs.add(dir_name)
                    results.append(FileInfo(
                        name=dir_name + "/",
                        path=path.rstrip("/") + "/" + dir_name,
                        type="dir",
                    ))
            else:
                results.append(self._file_info(file_path, file_data))

        return sorted(results, key=lambda x: (x.type == "file", x.name))

    def _file_info(self, path: str, data: dict) -> FileInfo:
        """Create FileInfo from file data."""
        content = data.get("content", "")
        return FileInfo(
            name=path.split("/")[-1],
            path=path,
            type="file",
            size=len(content.encode("utf-8")) if content else 0,
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else None,
            modified_at=datetime.fromisoformat(data["modified_at"]) if data.get("modified_at") else None,
        )

    def _get_all_files(self) -> dict:
        """Get all files from all stores."""
        files = {}

        # Thread state files
        for path, data in self._thread_state.get("files", {}).items():
            files[path] = data

        # Permanent store files (if available)
        if self._permanent_store or self._is_permanent_path("/memory/"):
            store = self._get_permanent_store()
            namespace = ("users", self.user_id, "filesystem")
            try:
                items = store.search(namespace, limit=1000)
                for item in items:
                    path = "/" + item.key
                    files[path] = item.value
            except Exception:
                pass

        return files

    # === Read (cat) ===

    def read(
        self,
        path: str,
        offset: int = 0,
        limit: int = 1000,
    ) -> str | None:
        """Read file contents."""
        path = self._normalize_path(path)
        data = self._get_file(path)

        if data is None:
            return None

        content = data.get("content", "")
        lines = content.split("\n")

        # Apply offset and limit
        selected = lines[offset:offset + limit]

        # Format with line numbers
        return "\n".join(
            f"{offset + i + 1:4d}\t{line}"
            for i, line in enumerate(selected)
        )

    def _get_file(self, path: str) -> dict | None:
        """Get file data from appropriate store."""
        if self._is_permanent_path(path):
            store = self._get_permanent_store()
            namespace = ("users", self.user_id, "filesystem")
            key = path.lstrip("/")
            item = store.get(namespace, key)
            return item.value if item else None
        else:
            return self._thread_state.get("files", {}).get(path)

    # === Write ===

    def write(
        self,
        path: str,
        content: str,
        append: bool = False,
    ) -> WriteResult:
        """Write content to file."""
        path = self._normalize_path(path)
        existing = self._get_file(path)

        if append and existing:
            content = existing.get("content", "") + content

        now = datetime.now(timezone.utc).isoformat()
        data = {
            "content": content,
            "created_at": existing.get("created_at", now) if existing else now,
            "modified_at": now,
        }

        if self._is_permanent_path(path):
            store = self._get_permanent_store()
            namespace = ("users", self.user_id, "filesystem")
            key = path.lstrip("/")
            store.put(namespace, key, data)
        else:
            if "files" not in self._thread_state:
                self._thread_state["files"] = {}
            self._thread_state["files"][path] = data

        return WriteResult(
            success=True,
            path=path,
            created=existing is None,
            bytes_written=len(content.encode("utf-8")),
        )

    # === Delete (rm) ===

    def rm(self, path: str, recursive: bool = False) -> bool:
        """Delete file or directory."""
        path = self._normalize_path(path)

        if recursive:
            # Delete all files under path
            all_files = self._get_all_files()
            deleted = False
            for file_path in list(all_files.keys()):
                if file_path == path or file_path.startswith(path + "/"):
                    self._delete_file(file_path)
                    deleted = True
            return deleted
        else:
            return self._delete_file(path)

    def _delete_file(self, path: str) -> bool:
        """Delete single file."""
        if self._is_permanent_path(path):
            store = self._get_permanent_store()
            namespace = ("users", self.user_id, "filesystem")
            key = path.lstrip("/")
            try:
                store.delete(namespace, key)
                return True
            except Exception:
                return False
        else:
            files = self._thread_state.get("files", {})
            if path in files:
                del files[path]
                return True
            return False

    # === Search (grep) ===

    def grep(
        self,
        pattern: str,
        path: str = "/",
        ignore_case: bool = False,
        context: int = 0,
    ) -> list[GrepMatch]:
        """Search file contents with regex."""
        path = self._normalize_path(path)
        flags = re.IGNORECASE if ignore_case else 0

        try:
            regex = re.compile(pattern, flags)
        except re.error:
            return []

        matches = []
        all_files = self._get_all_files()

        for file_path, data in all_files.items():
            # Check path filter
            if not (file_path == path or file_path.startswith(path + "/") or path == "/"):
                continue

            content = data.get("content", "")
            lines = content.split("\n")

            for i, line in enumerate(lines):
                if regex.search(line):
                    matches.append(GrepMatch(
                        path=file_path,
                        line_number=i + 1,
                        line=line,
                        context_before=lines[max(0, i - context):i] if context else [],
                        context_after=lines[i + 1:i + 1 + context] if context else [],
                    ))

        return matches

    # === Find ===

    def find(
        self,
        pattern: str,
        path: str = "/",
        type: str = "any",
    ) -> list[str]:
        """Find files by name pattern."""
        path = self._normalize_path(path)
        results = []

        for item in self.ls(path, recursive=True):
            if type == "file" and item.type != "file":
                continue
            if type == "dir" and item.type != "dir":
                continue

            name = item.name.rstrip("/")
            if fnmatch.fnmatch(name, pattern):
                results.append(item.path)

        return results

    # === Glob ===

    def glob(self, pattern: str) -> list[str]:
        """Match files with glob pattern."""
        all_files = self._get_all_files()
        results = []

        for file_path in all_files.keys():
            if fnmatch.fnmatch(file_path, pattern):
                results.append(file_path)

        return sorted(results)

    # === Copy ===

    def cp(self, src: str, dst: str) -> bool:
        """Copy file."""
        src = self._normalize_path(src)
        dst = self._normalize_path(dst)

        content_str = self.read(src)
        if content_str is None:
            return False

        # Strip line numbers from read output
        lines = []
        for line in content_str.split("\n"):
            if "\t" in line:
                lines.append(line.split("\t", 1)[1])
            else:
                lines.append(line)
        content = "\n".join(lines)

        result = self.write(dst, content)
        return result.success

    # === Move ===

    def mv(self, src: str, dst: str) -> bool:
        """Move/rename file."""
        if self.cp(src, dst):
            return self.rm(src)
        return False

    # === Existence checks ===

    def exists(self, path: str) -> bool:
        """Check if path exists."""
        path = self._normalize_path(path)
        return self._get_file(path) is not None or len(self.ls(path)) > 0

    def is_file(self, path: str) -> bool:
        """Check if path is a file."""
        path = self._normalize_path(path)
        return self._get_file(path) is not None

    def is_dir(self, path: str) -> bool:
        """Check if path is a directory."""
        path = self._normalize_path(path)
        if self._get_file(path) is not None:
            return False
        return len(self.ls(path)) > 0


# === Factory ===

def get_filesystem(
    user_id: str,
    thread_id: str | None = None,
    state: dict | None = None,
) -> VirtualFilesystem:
    """Get filesystem instance for user/thread."""
    import os
    from langgraph.store.memory import InMemoryStore

    # Use PostgresStore if DATABASE_URL is set
    permanent_store = None
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        try:
            from langgraph.store.postgres import PostgresStore
            permanent_store = PostgresStore.from_conn_string(database_url)
            permanent_store.setup()
        except Exception:
            permanent_store = InMemoryStore()
    else:
        permanent_store = InMemoryStore()

    return VirtualFilesystem(
        user_id=user_id,
        thread_id=thread_id,
        permanent_store=permanent_store,
        thread_state=state or {},
    )
```

## Workflow Integration

### Using Filesystem in Nodes

```python
# apps/api/workflow/nodes/drafting.py

async def drafting_node(state: dict) -> dict:
    """Generate resume draft using filesystem."""
    from services.virtual_filesystem import VirtualFilesystem

    user_id = state.get("user_id", "anonymous")
    fs = VirtualFilesystem(user_id=user_id, thread_state=state)

    # Read user preferences from memory
    prefs = fs.read("/memory/preferences.md")

    # Read research data from working files
    profile = fs.read("/research/profile.json")
    job = fs.read("/research/job.json")
    gap_analysis = fs.read("/research/gap_analysis.json")

    # Generate draft...
    draft_html = await generate_draft_with_llm(
        profile=profile,
        job=job,
        gap_analysis=gap_analysis,
        preferences=prefs,
    )

    # Write draft to filesystem
    fs.write("/drafts/current.html", draft_html)

    # Copy to versioned file
    version = state.get("draft_version", 1)
    fs.write(f"/drafts/v{version}.html", draft_html)

    return {
        "draft_html": draft_html,
        "draft_version": version,
        "current_step": "editor",
        **state,
    }
```

### Agent Tools

```python
# apps/api/tools/filesystem_tools.py

from langchain_core.tools import tool
from services.virtual_filesystem import VirtualFilesystem

@tool
def fs_ls(path: str = "/", recursive: bool = False) -> str:
    """List files and directories.

    Args:
        path: Directory path to list (default: root)
        recursive: Include subdirectories

    Returns:
        Formatted directory listing
    """
    fs = get_current_filesystem()  # From context
    items = fs.ls(path, recursive=recursive)

    lines = []
    for item in items:
        size = f"{item.size:>8}" if item.size else "       -"
        lines.append(f"{item.type[0]} {size} {item.path}")

    return "\n".join(lines) or "(empty)"

@tool
def fs_read(path: str) -> str:
    """Read file contents.

    Args:
        path: Path to file

    Returns:
        File contents with line numbers
    """
    fs = get_current_filesystem()
    content = fs.read(path)
    return content if content else f"Error: {path} not found"

@tool
def fs_write(path: str, content: str, append: bool = False) -> str:
    """Write content to file.

    Args:
        path: Path to file
        content: Content to write
        append: Append to existing file instead of overwrite

    Returns:
        Success message
    """
    fs = get_current_filesystem()
    result = fs.write(path, content, append=append)

    if result.success:
        action = "appended to" if not result.created else "created"
        return f"Successfully {action} {path} ({result.bytes_written} bytes)"
    return f"Error writing to {path}"

@tool
def fs_grep(pattern: str, path: str = "/") -> str:
    """Search file contents.

    Args:
        pattern: Regex pattern to search
        path: Path to search in

    Returns:
        Matching lines with context
    """
    fs = get_current_filesystem()
    matches = fs.grep(pattern, path)

    if not matches:
        return f"No matches for '{pattern}'"

    lines = []
    for m in matches[:20]:  # Limit results
        lines.append(f"{m.path}:{m.line_number}: {m.line}")

    return "\n".join(lines)

@tool
def fs_find(pattern: str, path: str = "/") -> str:
    """Find files by name.

    Args:
        pattern: Glob pattern for filename
        path: Directory to search

    Returns:
        List of matching paths
    """
    fs = get_current_filesystem()
    results = fs.find(pattern, path)

    return "\n".join(results) if results else f"No files matching '{pattern}'"
```

## LangSmith Evaluation

### Test Data

```python
# apps/api/tests/eval_data/filesystem_examples.py

FILESYSTEM_EXAMPLES = [
    # Memory read/write
    {
        "id": "memory-preferences-roundtrip",
        "operations": [
            {"op": "write", "path": "/memory/preferences.md", "content": "tone: formal\nstructure: bullets"},
            {"op": "read", "path": "/memory/preferences.md"},
        ],
        "expected": {
            "read_contains": "tone: formal",
            "persists": True,
        },
    },
    # Draft versioning
    {
        "id": "draft-version-flow",
        "operations": [
            {"op": "write", "path": "/drafts/current.html", "content": "<h1>Draft 1</h1>"},
            {"op": "cp", "src": "/drafts/current.html", "dst": "/drafts/v1.html"},
            {"op": "write", "path": "/drafts/current.html", "content": "<h1>Draft 2</h1>"},
            {"op": "ls", "path": "/drafts/"},
        ],
        "expected": {
            "file_count": 2,
            "files_contain": ["current.html", "v1.html"],
        },
    },
    # Search across files
    {
        "id": "grep-across-research",
        "operations": [
            {"op": "write", "path": "/research/profile.json", "content": '{"skills": ["Python", "JavaScript"]}'},
            {"op": "write", "path": "/research/job.json", "content": '{"requirements": ["Python", "React"]}'},
            {"op": "grep", "pattern": "Python", "path": "/research/"},
        ],
        "expected": {
            "match_count": 2,
            "paths_contain": ["/research/profile.json", "/research/job.json"],
        },
    },
]

WORKFLOW_INTEGRATION_EXAMPLES = [
    {
        "id": "drafting-uses-memory",
        "setup": {
            "memory_content": "tone: confident\nfirst_person: false\nemphasis: quantified achievements",
            "profile": {"name": "Test User", "skills": ["Python"]},
            "job": {"title": "Engineer", "company": "Acme"},
        },
        "expected_draft": {
            "tone": "confident",
            "no_first_person": True,
            "has_metrics": True,
        },
    },
    {
        "id": "research-stores-to-fs",
        "setup": {
            "linkedin_url": "https://linkedin.com/in/test",
            "job_url": "https://jobs.example.com/swe",
        },
        "expected_files": [
            "/research/profile.json",
            "/research/job.json",
            "/research/company.md",
            "/research/gap_analysis.json",
        ],
    },
]
```

### Evaluators

```python
# apps/api/tests/evaluators/filesystem_evaluators.py

from openevals.llm import create_llm_as_judge

# === Filesystem Operation Correctness ===

FS_CORRECTNESS_PROMPT = """Evaluate if the filesystem operations produced correct results.

Operations performed:
{operations}

Results:
{results}

Expected:
{expected}

Evaluate:
1. Did read operations return expected content?
2. Did write operations succeed?
3. Did search operations find expected matches?
4. Is the filesystem state consistent?

Return JSON:
{{
    "score": <0.0 to 1.0>,
    "correct_operations": <count>,
    "total_operations": <count>,
    "errors": ["<list of errors>"]
}}
"""

fs_correctness_evaluator = create_llm_as_judge(
    prompt=FS_CORRECTNESS_PROMPT,
    model="anthropic:claude-sonnet-4-20250514",
)

# === Memory Utilization ===

MEMORY_UTILIZATION_PROMPT = """Evaluate if the agent effectively used the filesystem for memory.

Available memory files:
{memory_files}

Task:
{task}

Agent actions:
{actions}

Agent output:
{output}

Evaluate:
1. Did agent read relevant memory files?
2. Did agent apply memory content appropriately?
3. Did agent update memory when learning something new?
4. Was memory used efficiently (not over-reading)?

Return JSON:
{{
    "score": <0.0 to 1.0>,
    "memory_read": <true/false>,
    "memory_applied": <true/false>,
    "memory_updated": <true/false>,
    "reasoning": "<explanation>"
}}
"""

memory_utilization_evaluator = create_llm_as_judge(
    prompt=MEMORY_UTILIZATION_PROMPT,
    model="anthropic:claude-sonnet-4-20250514",
)

# === Draft Quality with Memory ===

DRAFT_WITH_MEMORY_PROMPT = """Evaluate the quality of a draft generated using user memory.

User memory:
{memory}

User profile:
{profile}

Target job:
{job}

Generated draft:
{draft}

Evaluate:
1. Does the draft follow tone preferences from memory?
2. Does it follow structure preferences?
3. Does it emphasize what the user wants emphasized?
4. Is it relevant to the job?
5. Is it professional and well-written?

Return JSON:
{{
    "overall_score": <0.0 to 1.0>,
    "preference_adherence": <0.0 to 1.0>,
    "job_relevance": <0.0 to 1.0>,
    "quality": <0.0 to 1.0>,
    "violations": ["<preference violations>"],
    "reasoning": "<explanation>"
}}
"""

draft_with_memory_evaluator = create_llm_as_judge(
    prompt=DRAFT_WITH_MEMORY_PROMPT,
    model="anthropic:claude-sonnet-4-20250514",
)
```

### Pytest Tests

```python
# apps/api/tests/test_filesystem_evals.py

import pytest
from langsmith import evaluate

from tests.eval_data.filesystem_examples import (
    FILESYSTEM_EXAMPLES,
    WORKFLOW_INTEGRATION_EXAMPLES,
)
from tests.evaluators.filesystem_evaluators import (
    fs_correctness_evaluator,
    memory_utilization_evaluator,
    draft_with_memory_evaluator,
)
from services.virtual_filesystem import VirtualFilesystem


class TestFilesystemOperations:
    """Test core filesystem operations."""

    @pytest.mark.parametrize("example", FILESYSTEM_EXAMPLES, ids=lambda x: x["id"])
    def test_filesystem_operations(self, example):
        """Test filesystem operation sequences."""
        fs = VirtualFilesystem(user_id="test-user")
        results = []

        for op in example["operations"]:
            if op["op"] == "write":
                result = fs.write(op["path"], op["content"])
                results.append({"op": "write", "success": result.success})
            elif op["op"] == "read":
                result = fs.read(op["path"])
                results.append({"op": "read", "content": result})
            elif op["op"] == "ls":
                result = fs.ls(op["path"])
                results.append({"op": "ls", "files": [f.name for f in result]})
            elif op["op"] == "grep":
                result = fs.grep(op["pattern"], op.get("path", "/"))
                results.append({"op": "grep", "matches": len(result)})
            elif op["op"] == "cp":
                result = fs.cp(op["src"], op["dst"])
                results.append({"op": "cp", "success": result})

        # Verify expected outcomes
        expected = example["expected"]
        if "read_contains" in expected:
            read_result = next(r for r in results if r["op"] == "read")
            assert expected["read_contains"] in read_result["content"]

        if "file_count" in expected:
            ls_result = next(r for r in results if r["op"] == "ls")
            assert len(ls_result["files"]) == expected["file_count"]

        if "match_count" in expected:
            grep_result = next(r for r in results if r["op"] == "grep")
            assert grep_result["matches"] == expected["match_count"]


class TestWorkflowIntegration:
    """Test filesystem integration with workflow."""

    @pytest.mark.langsmith(
        dataset_name="filesystem-workflow-evals",
        experiment_prefix="fs-workflow-v1",
    )
    @pytest.mark.parametrize("example", WORKFLOW_INTEGRATION_EXAMPLES, ids=lambda x: x["id"])
    async def test_drafting_uses_memory(self, example):
        """Test that drafting correctly uses filesystem memory."""
        from workflow.nodes.drafting import generate_draft_with_memory

        setup = example["setup"]

        # Setup filesystem
        fs = VirtualFilesystem(user_id="test-user")
        fs.write("/memory/preferences.md", setup.get("memory_content", ""))

        # Generate draft
        draft = await generate_draft_with_memory(
            fs=fs,
            profile=setup["profile"],
            job=setup["job"],
        )

        # Evaluate with LLM judge
        result = draft_with_memory_evaluator(
            inputs={
                "memory": setup.get("memory_content", ""),
                "profile": setup["profile"],
                "job": setup["job"],
            },
            outputs={"draft": draft},
        )

        expected = example["expected_draft"]
        assert result["preference_adherence"] >= 0.7
        assert result["overall_score"] >= 0.7

        return result


class TestMemoryPersistence:
    """Test memory persistence across operations."""

    def test_memory_persists_after_write(self):
        """Memory should persist in permanent store."""
        fs1 = VirtualFilesystem(user_id="persist-test")
        fs1.write("/memory/test.md", "persistent content")

        # New instance, same user
        fs2 = VirtualFilesystem(user_id="persist-test")
        content = fs2.read("/memory/test.md")

        assert content is not None
        assert "persistent content" in content

    def test_drafts_scoped_to_thread(self):
        """Drafts should be thread-scoped, not shared."""
        state1 = {}
        state2 = {}

        fs1 = VirtualFilesystem(user_id="thread-test", thread_state=state1)
        fs1.write("/drafts/current.html", "draft from thread 1")

        fs2 = VirtualFilesystem(user_id="thread-test", thread_state=state2)
        content = fs2.read("/drafts/current.html")

        # Should not see draft from other thread
        assert content is None
```

## Success Criteria

### Filesystem Operations

- [ ] `ls("/")` lists root directories
- [ ] `ls("/drafts/", recursive=True)` lists all drafts
- [ ] `read(path)` returns content with line numbers
- [ ] `write(path, content)` creates/updates files
- [ ] `write(path, content, append=True)` appends
- [ ] `rm(path)` deletes files
- [ ] `rm(path, recursive=True)` deletes directories
- [ ] `grep(pattern, path)` searches with regex
- [ ] `find(pattern, path)` finds by filename
- [ ] `glob(pattern)` matches glob patterns
- [ ] `cp(src, dst)` copies files
- [ ] `mv(src, dst)` moves files

### Storage Routing

- [ ] `/memory/**` routes to permanent store
- [ ] `/drafts/**` routes to thread state
- [ ] `/research/**` routes to thread state
- [ ] `/tmp/**` routes to thread state
- [ ] Memory persists across sessions
- [ ] Drafts are thread-scoped

### Workflow Integration

- [ ] Drafting node reads memory preferences
- [ ] Drafting node writes to `/drafts/`
- [ ] Research node writes to `/research/`
- [ ] Export node writes to `/exports/`
- [ ] Agent tools work correctly

### LangSmith Evaluation

- [ ] Tests tracked in LangSmith
- [ ] LLM-as-judge evaluators work
- [ ] Quality thresholds enforced (>= 0.7)

## Implementation Order

1. **Phase 1**: Core VirtualFilesystem class (ls, read, write, rm)
2. **Phase 2**: Search operations (grep, find, glob)
3. **Phase 3**: File operations (cp, mv)
4. **Phase 4**: Storage routing (permanent vs thread)
5. **Phase 5**: Workflow node integration
6. **Phase 6**: Agent tools
7. **Phase 7**: LangSmith evaluators and tests

## References

- [deepagents backends](https://github.com/langchain-ai/deepagents/tree/main/libs/deepagents/deepagents/backends)
- [LangGraph BaseStore](https://langchain-ai.github.io/langgraph/reference/store/)
- [LangSmith Pytest Integration](https://docs.langchain.com/langsmith/pytest-integration)
- [OpenEvals](https://github.com/langchain-ai/openevals)
