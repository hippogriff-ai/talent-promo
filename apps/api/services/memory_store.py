"""In-memory store service with file system metaphor.

This service follows Harrison Chase's patterns:
- Memory as file system: namespaces as folders, keys as filenames
- Three memory types: Procedural, Semantic, Episodic (COALA paper)
- InMemoryStore only (no persistence - privacy by design)

Namespace structure:
    ("users", user_id, "procedural")  - System prompts, preferences
    ("users", user_id, "semantic")    - Extracted knowledge, facts
    ("users", user_id, "episodic")    - Past experiences, events

File system exposure:
    /users/{user_id}/MEMORY.md         - Aggregated markdown view
    /users/{user_id}/procedural/*.json - Preferences
    /users/{user_id}/semantic/*.json   - Facts
    /users/{user_id}/episodic/*.json   - Events
"""

import json
import logging
from datetime import datetime, timezone
from typing import Literal, Optional

from pydantic import BaseModel
from langgraph.store.memory import InMemoryStore

logger = logging.getLogger(__name__)

MemoryType = Literal["procedural", "semantic", "episodic"]


class MemoryItem(BaseModel):
    """A memory item stored in the LangGraph Store."""

    key: str
    namespace: tuple[str, ...]
    value: dict
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class MemoryStoreService:
    """In-memory store with file system metaphor.

    - Namespaces = folders (hierarchical paths)
    - Keys = filenames (unique identifiers)
    - Values = JSON documents
    """

    def __init__(self):
        """Initialize the memory store with InMemoryStore."""
        self._store: Optional[InMemoryStore] = None

    def _get_store(self) -> InMemoryStore:
        """Get or create the InMemoryStore instance."""
        if self._store is None:
            self._store = InMemoryStore()
            logger.info("Using InMemoryStore (no persistence - privacy by design)")
        return self._store

    def _namespace(self, user_id: str, memory_type: MemoryType) -> tuple[str, ...]:
        """Build namespace tuple: ("users", user_id, memory_type)."""
        return ("users", user_id, memory_type)

    # ==================== Core Operations ====================

    def put(self, user_id: str, memory_type: MemoryType, key: str, value: dict) -> bool:
        """Store a memory item."""
        try:
            store = self._get_store()
            ns = self._namespace(user_id, memory_type)

            now = datetime.now(timezone.utc).isoformat()
            enriched = {
                **value,
                "_created_at": value.get("_created_at", now),
                "_updated_at": now,
            }

            store.put(ns, key, enriched)
            return True
        except Exception as e:
            logger.error(f"put failed: {e}")
            return False

    def get(self, user_id: str, memory_type: MemoryType, key: str) -> Optional[dict]:
        """Retrieve a memory item."""
        try:
            store = self._get_store()
            ns = self._namespace(user_id, memory_type)
            item = store.get(ns, key)
            return item.value if item else None
        except Exception as e:
            logger.error(f"get failed: {e}")
            return None

    def delete(self, user_id: str, memory_type: MemoryType, key: str) -> bool:
        """Delete a memory item."""
        try:
            store = self._get_store()
            ns = self._namespace(user_id, memory_type)
            store.delete(ns, key)
            return True
        except Exception as e:
            logger.error(f"delete failed: {e}")
            return False

    def list_keys(self, user_id: str, memory_type: MemoryType, limit: int = 100) -> list[str]:
        """List all keys in a namespace."""
        try:
            store = self._get_store()
            ns = self._namespace(user_id, memory_type)
            items = store.search(ns, limit=limit)
            return [item.key for item in items]
        except Exception as e:
            logger.error(f"list_keys failed: {e}")
            return []

    def search(
        self,
        user_id: str,
        memory_type: MemoryType,
        filter: Optional[dict] = None,
        limit: int = 10,
    ) -> list[MemoryItem]:
        """Search memory items with optional filter."""
        try:
            store = self._get_store()
            ns = self._namespace(user_id, memory_type)
            items = store.search(ns, filter=filter, limit=limit)
            return [
                MemoryItem(
                    key=item.key,
                    namespace=item.namespace,
                    value=item.value,
                    created_at=datetime.fromisoformat(item.value["_created_at"])
                    if item.value.get("_created_at")
                    else None,
                    updated_at=datetime.fromisoformat(item.value["_updated_at"])
                    if item.value.get("_updated_at")
                    else None,
                )
                for item in items
            ]
        except Exception as e:
            logger.error(f"search failed: {e}")
            return []

    # ==================== Procedural Memory (Preferences) ====================

    def save_preferences(self, user_id: str, preferences: dict) -> bool:
        """Save user preferences."""
        return self.put(user_id, "procedural", "preferences", {"type": "preferences", **preferences})

    def get_preferences(self, user_id: str) -> Optional[dict]:
        """Get user preferences (excludes internal fields)."""
        value = self.get(user_id, "procedural", "preferences")
        if value:
            return {k: v for k, v in value.items() if not k.startswith("_")}
        return None

    # ==================== Semantic Memory (Facts) ====================

    def save_fact(self, user_id: str, fact_id: str, fact: dict) -> bool:
        """Save a learned fact."""
        return self.put(user_id, "semantic", fact_id, {"type": "fact", **fact})

    def get_facts(self, user_id: str, limit: int = 50) -> list[dict]:
        """Get all facts for a user."""
        items = self.search(user_id, "semantic", limit=limit)
        return [item.value for item in items]

    # ==================== Episodic Memory (Events) ====================

    def record_event(
        self,
        user_id: str,
        event_type: str,
        event_data: dict,
        thread_id: Optional[str] = None,
    ) -> bool:
        """Record an event."""
        import uuid

        event_id = str(uuid.uuid4())
        return self.put(
            user_id,
            "episodic",
            event_id,
            {"type": event_type, "thread_id": thread_id, **event_data},
        )

    def get_recent_events(
        self,
        user_id: str,
        event_type: Optional[str] = None,
        limit: int = 20,
    ) -> list[dict]:
        """Get recent events, sorted by time descending."""
        filter_dict = {"type": event_type} if event_type else None
        items = self.search(user_id, "episodic", filter=filter_dict, limit=limit)

        sorted_items = sorted(
            items,
            key=lambda x: x.updated_at or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )
        return [item.value for item in sorted_items]

    # ==================== File System Exposure ====================

    def expose_as_filesystem(self, user_id: str) -> dict[str, str]:
        """Expose user memory as virtual file system.

        Returns dict mapping paths to content:
            /MEMORY.md -> markdown summary
            /procedural/preferences.json -> JSON
            /semantic/{fact_id}.json -> JSON
            /episodic/{event_id}.json -> JSON
        """
        files: dict[str, str] = {}

        # Export each memory type as JSON files
        for memory_type in ("procedural", "semantic", "episodic"):
            keys = self.list_keys(user_id, memory_type, limit=1000)  # type: ignore
            for key in keys:
                value = self.get(user_id, memory_type, key)  # type: ignore
                if value:
                    path = f"/{memory_type}/{key}.json"
                    files[path] = json.dumps(value, indent=2, default=str)

        # Generate MEMORY.md summary
        files["/MEMORY.md"] = self._generate_memory_md(user_id)

        return files

    def _generate_memory_md(self, user_id: str) -> str:
        """Generate markdown summary of user memory."""
        lines = [
            f"# Memory for {user_id}",
            f"_Generated: {datetime.now(timezone.utc).isoformat()}_",
            "",
            "## Preferences",
        ]

        prefs = self.get_preferences(user_id)
        if prefs:
            for k, v in prefs.items():
                if k != "type":
                    lines.append(f"- **{k}**: {v}")
        else:
            lines.append("_None_")

        lines.extend(["", "## Facts"])
        facts = self.get_facts(user_id, limit=20)
        if facts:
            for f in facts:
                lines.append(f"- {f.get('value', f)}")
        else:
            lines.append("_None_")

        lines.extend(["", "## Recent Events"])
        events = self.get_recent_events(user_id, limit=10)
        if events:
            for e in events:
                ts = e.get("_updated_at", "")[:16] if e.get("_updated_at") else "?"
                lines.append(f"- [{ts}] {e.get('type', 'event')}")
        else:
            lines.append("_None_")

        return "\n".join(lines)

    def get_memory_context_for_prompt(self, user_id: str) -> str:
        """Get memory formatted for LLM prompt injection."""
        lines = ["<user_memory>"]

        prefs = self.get_preferences(user_id)
        if prefs:
            lines.append("Preferences:")
            for k, v in prefs.items():
                if k != "type":
                    lines.append(f"  {k}: {v}")

        facts = self.get_facts(user_id, limit=5)
        if facts:
            lines.append("Facts:")
            for f in facts:
                lines.append(f"  - {f.get('value', f)}")

        lines.append("</user_memory>")
        return "\n".join(lines)

    # ==================== User Data Management ====================

    def delete_all_user_data(self, user_id: str) -> bool:
        """Delete all memory for a user (GDPR)."""
        success = True
        for memory_type in ("procedural", "semantic", "episodic"):
            for key in self.list_keys(user_id, memory_type, limit=1000):  # type: ignore
                if not self.delete(user_id, memory_type, key):  # type: ignore
                    success = False
        return success

    def export_user_data(self, user_id: str) -> dict:
        """Export all memory for a user (GDPR)."""
        return {
            mt: [self.get(user_id, mt, k) for k in self.list_keys(user_id, mt, limit=1000)]  # type: ignore
            for mt in ("procedural", "semantic", "episodic")
        }

    def close(self):
        """Close store (no-op for in-memory)."""
        self._store = None


# Singleton
_memory_store: Optional[MemoryStoreService] = None


def get_memory_store() -> MemoryStoreService:
    """Get singleton MemoryStoreService instance."""
    global _memory_store
    if _memory_store is None:
        _memory_store = MemoryStoreService()
    return _memory_store


def reset_memory_store():
    """Reset singleton (for testing)."""
    global _memory_store
    if _memory_store:
        _memory_store.close()
    _memory_store = None
