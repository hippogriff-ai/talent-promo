"""Tests for LangGraph Store-based memory service.

Tests the file system metaphor memory implementation following
Harrison Chase's patterns for agent memory.
"""

import pytest
from datetime import datetime, timezone

from services.memory_store import (
    MemoryStoreService,
    MemoryItem,
    get_memory_store,
    reset_memory_store,
)


class TestCoreOperations:
    """Test basic Store operations."""

    def test_put_and_get(self):
        """Store and retrieve a value."""
        service = MemoryStoreService()
        user_id = "test-user-1"

        result = service.put(user_id, "procedural", "test-key", {"data": "test-value"})
        assert result is True

        value = service.get(user_id, "procedural", "test-key")
        assert value is not None
        assert value["data"] == "test-value"
        assert "_created_at" in value
        assert "_updated_at" in value

    def test_get_nonexistent(self):
        """Get nonexistent key returns None."""
        service = MemoryStoreService()
        value = service.get("no-user", "procedural", "no-key")
        assert value is None

    def test_delete(self):
        """Delete removes item."""
        service = MemoryStoreService()
        user_id = "test-user-2"

        service.put(user_id, "semantic", "fact-1", {"type": "skill"})
        assert service.get(user_id, "semantic", "fact-1") is not None

        result = service.delete(user_id, "semantic", "fact-1")
        assert result is True
        assert service.get(user_id, "semantic", "fact-1") is None

    def test_list_keys(self):
        """List keys returns all keys in namespace."""
        service = MemoryStoreService()
        user_id = "test-user-3"

        service.put(user_id, "episodic", "event-1", {"type": "edit"})
        service.put(user_id, "episodic", "event-2", {"type": "accept"})
        service.put(user_id, "episodic", "event-3", {"type": "reject"})

        keys = service.list_keys(user_id, "episodic")
        assert len(keys) == 3
        assert set(keys) == {"event-1", "event-2", "event-3"}


class TestNamespaceIsolation:
    """Test namespace organization (file system metaphor)."""

    def test_memory_type_isolation(self):
        """Different memory types don't conflict."""
        service = MemoryStoreService()
        user_id = "test-user-4"

        service.put(user_id, "procedural", "config", {"setting": "procedural"})
        service.put(user_id, "semantic", "config", {"setting": "semantic"})
        service.put(user_id, "episodic", "config", {"setting": "episodic"})

        assert service.get(user_id, "procedural", "config")["setting"] == "procedural"
        assert service.get(user_id, "semantic", "config")["setting"] == "semantic"
        assert service.get(user_id, "episodic", "config")["setting"] == "episodic"

    def test_user_isolation(self):
        """Different users don't conflict."""
        service = MemoryStoreService()

        service.put("user-a", "procedural", "prefs", {"tone": "formal"})
        service.put("user-b", "procedural", "prefs", {"tone": "casual"})

        assert service.get("user-a", "procedural", "prefs")["tone"] == "formal"
        assert service.get("user-b", "procedural", "prefs")["tone"] == "casual"


class TestProceduralMemory:
    """Test procedural memory (preferences)."""

    def test_save_and_get_preferences(self):
        """Save and retrieve preferences."""
        service = MemoryStoreService()
        user_id = "test-user-5"

        preferences = {
            "tone": "confident",
            "structure": "bullets",
            "first_person": False,
        }

        result = service.save_preferences(user_id, preferences)
        assert result is True

        retrieved = service.get_preferences(user_id)
        assert retrieved is not None
        assert retrieved["tone"] == "confident"
        assert "_created_at" not in retrieved  # Internal fields excluded

    def test_update_preferences(self):
        """Update existing preferences."""
        service = MemoryStoreService()
        user_id = "test-user-6"

        service.save_preferences(user_id, {"tone": "formal"})
        assert service.get_preferences(user_id)["tone"] == "formal"

        service.save_preferences(user_id, {"tone": "casual", "structure": "paragraphs"})
        prefs = service.get_preferences(user_id)
        assert prefs["tone"] == "casual"
        assert prefs["structure"] == "paragraphs"


class TestSemanticMemory:
    """Test semantic memory (facts)."""

    def test_save_and_get_facts(self):
        """Save and retrieve facts."""
        service = MemoryStoreService()
        user_id = "test-user-7"

        service.save_fact(user_id, "skill-1", {"category": "language", "value": "Python"})
        service.save_fact(user_id, "skill-2", {"category": "framework", "value": "FastAPI"})

        facts = service.get_facts(user_id)
        assert len(facts) == 2
        categories = {f["category"] for f in facts}
        assert categories == {"language", "framework"}


class TestEpisodicMemory:
    """Test episodic memory (events)."""

    def test_record_and_get_events(self):
        """Record and retrieve events."""
        service = MemoryStoreService()
        user_id = "test-user-8"

        service.record_event(user_id, "edit", {"section": "summary"}, thread_id="thread-1")
        service.record_event(user_id, "suggestion_accept", {"suggestion_id": "s1"})

        events = service.get_recent_events(user_id)
        assert len(events) == 2
        event_types = {e["type"] for e in events}
        assert event_types == {"edit", "suggestion_accept"}


class TestFileSystemExposure:
    """Test file system exposure (Harrison Chase pattern)."""

    def test_expose_as_filesystem(self):
        """Expose memory as virtual filesystem."""
        service = MemoryStoreService()
        user_id = "fs-test-1"

        service.save_preferences(user_id, {"tone": "formal"})
        service.save_fact(user_id, "skill-python", {"value": "Python"})
        service.record_event(user_id, "edit", {"section": "summary"})

        files = service.expose_as_filesystem(user_id)

        assert "/MEMORY.md" in files
        assert "/procedural/preferences.json" in files
        assert "/semantic/skill-python.json" in files
        # Episodic has UUID keys
        episodic_files = [k for k in files if k.startswith("/episodic/")]
        assert len(episodic_files) >= 1

    def test_memory_md_content(self):
        """MEMORY.md contains all sections."""
        service = MemoryStoreService()
        user_id = "fs-test-2"

        service.save_preferences(user_id, {"tone": "confident"})
        service.save_fact(user_id, "company", {"value": "Google"})

        files = service.expose_as_filesystem(user_id)
        md = files["/MEMORY.md"]

        assert f"# Memory for {user_id}" in md
        assert "## Preferences" in md
        assert "## Facts" in md
        assert "## Recent Events" in md
        assert "confident" in md
        assert "Google" in md


class TestMemoryContextForPrompt:
    """Test memory context for LLM prompts."""

    def test_context_with_data(self):
        """Context includes preferences and facts."""
        service = MemoryStoreService()
        user_id = "ctx-test-1"

        service.save_preferences(user_id, {"tone": "confident"})
        service.save_fact(user_id, "skill", {"value": "Python expert"})

        context = service.get_memory_context_for_prompt(user_id)

        assert "<user_memory>" in context
        assert "</user_memory>" in context
        assert "tone: confident" in context
        assert "Python expert" in context

    def test_context_empty(self):
        """Context with no data is minimal."""
        service = MemoryStoreService()
        context = service.get_memory_context_for_prompt("empty-user")

        assert "<user_memory>" in context
        assert "</user_memory>" in context
        assert "Preferences:" not in context


class TestUserDataManagement:
    """Test GDPR compliance features."""

    def test_export_user_data(self):
        """Export includes all memory types."""
        service = MemoryStoreService()
        user_id = "gdpr-test-1"

        service.save_preferences(user_id, {"tone": "formal"})
        service.save_fact(user_id, "fact-1", {"value": "Python"})
        service.record_event(user_id, "edit", {"section": "summary"})

        data = service.export_user_data(user_id)
        assert "procedural" in data
        assert "semantic" in data
        assert "episodic" in data
        assert len(data["procedural"]) >= 1

    def test_delete_all_user_data(self):
        """Delete removes all user memory."""
        service = MemoryStoreService()
        user_id = "gdpr-test-2"

        service.save_preferences(user_id, {"tone": "formal"})
        service.save_fact(user_id, "fact-1", {"value": "test"})
        service.record_event(user_id, "edit", {"data": "test"})

        assert service.get_preferences(user_id) is not None

        result = service.delete_all_user_data(user_id)
        assert result is True

        assert service.get_preferences(user_id) is None
        assert len(service.get_facts(user_id)) == 0
        assert len(service.get_recent_events(user_id)) == 0


class TestSingleton:
    """Test singleton pattern."""

    def test_get_returns_same_instance(self):
        """Singleton returns same instance."""
        reset_memory_store()
        store1 = get_memory_store()
        store2 = get_memory_store()
        assert store1 is store2

    def test_reset_creates_new_instance(self):
        """Reset creates new instance."""
        store1 = get_memory_store()
        reset_memory_store()
        store2 = get_memory_store()
        assert store1 is not store2


class TestTimestamps:
    """Test timestamp handling."""

    def test_created_at_preserved_on_update(self):
        """created_at preserved when updating."""
        service = MemoryStoreService()
        user_id = "ts-test-1"

        service.put(user_id, "procedural", "test", {"value": 1})
        initial = service.get(user_id, "procedural", "test")
        created_at = initial["_created_at"]

        service.put(user_id, "procedural", "test", {"value": 2, "_created_at": created_at})
        updated = service.get(user_id, "procedural", "test")

        assert updated["_created_at"] == created_at
        assert updated["value"] == 2


class TestSearch:
    """Test search functionality."""

    def test_search_returns_memory_items(self):
        """Search returns MemoryItem objects."""
        service = MemoryStoreService()
        user_id = "search-test-1"

        service.put(user_id, "semantic", "item-1", {"category": "skill"})
        service.put(user_id, "semantic", "item-2", {"category": "experience"})

        items = service.search(user_id, "semantic", limit=10)
        assert len(items) == 2
        assert all(isinstance(item, MemoryItem) for item in items)
        assert all(item.namespace == ("users", user_id, "semantic") for item in items)
