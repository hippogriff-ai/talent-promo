"""In-Memory Thread Metadata Service for tracking workflow lifecycle.

This service manages thread metadata in-memory:
- Thread creation and access times
- Thread expiration for cleanup (2 hours default)
- Workflow status and step

Privacy by design: All data is ephemeral and cleaned up automatically.
"""

import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# Default TTL for threads (2 hours)
DEFAULT_TTL_HOURS = float(os.getenv("THREAD_TTL_HOURS", "2"))


class ThreadMetadata:
    """In-memory thread metadata record."""

    def __init__(
        self,
        thread_id: str,
        workflow_step: str = "ingest",
        user_id: Optional[str] = None,
        ttl_hours: Optional[float] = None,
    ):
        now = datetime.now(timezone.utc)
        ttl = ttl_hours or DEFAULT_TTL_HOURS

        self.thread_id = thread_id
        self.created_at = now
        self.last_accessed_at = now
        self.expires_at = now + timedelta(hours=ttl)
        self.user_id = user_id
        self.status = "active"
        self.workflow_step = workflow_step
        self.metadata: dict = {}

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "thread_id": self.thread_id,
            "created_at": self.created_at.isoformat(),
            "last_accessed_at": self.last_accessed_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "user_id": self.user_id,
            "status": self.status,
            "workflow_step": self.workflow_step,
            "metadata": self.metadata,
        }


class ThreadMetadataService:
    """In-memory service for managing thread metadata with automatic cleanup."""

    def __init__(self):
        """Initialize the service with in-memory storage."""
        self._threads: dict[str, ThreadMetadata] = {}
        self._cleanup_task: Optional[asyncio.Task] = None
        self._cleanup_interval_seconds = 300  # Check every 5 minutes
        logger.info(f"ThreadMetadataService initialized (TTL: {DEFAULT_TTL_HOURS}h)")

    def start_cleanup_task(self):
        """Start the background cleanup task."""
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
            logger.info("Started thread cleanup background task")

    async def _cleanup_loop(self):
        """Background loop that cleans up expired threads."""
        while True:
            try:
                await asyncio.sleep(self._cleanup_interval_seconds)
                result = self.cleanup_expired_threads()
                if result["deleted"] > 0:
                    logger.info(f"Cleaned up {result['deleted']} expired threads")
            except asyncio.CancelledError:
                logger.info("Thread cleanup task cancelled")
                break
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")

    def stop_cleanup_task(self):
        """Stop the background cleanup task."""
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            self._cleanup_task = None

    def create_thread(
        self,
        thread_id: str,
        workflow_step: str = "ingest",
        user_id: Optional[str] = None,
        ttl_hours: Optional[float] = None,
    ) -> bool:
        """Create a new thread metadata record.

        Args:
            thread_id: The workflow thread ID
            workflow_step: Initial workflow step (default: ingest)
            user_id: Optional user ID for multi-tenant support
            ttl_hours: Custom TTL in hours (default: DEFAULT_TTL_HOURS)

        Returns:
            True if created successfully.
        """
        try:
            self._threads[thread_id] = ThreadMetadata(
                thread_id=thread_id,
                workflow_step=workflow_step,
                user_id=user_id,
                ttl_hours=ttl_hours,
            )
            logger.info(f"Created thread metadata for {thread_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to create thread metadata: {e}")
            return False

    def update_last_accessed(self, thread_id: str, workflow_step: Optional[str] = None) -> bool:
        """Update the last_accessed_at timestamp for a thread.

        Args:
            thread_id: The workflow thread ID
            workflow_step: Optional new workflow step

        Returns:
            True if updated successfully.
        """
        thread = self._threads.get(thread_id)
        if not thread:
            return False

        thread.last_accessed_at = datetime.now(timezone.utc)
        if workflow_step:
            thread.workflow_step = workflow_step
        return True

    def update_status(self, thread_id: str, status: str) -> bool:
        """Update the status of a thread.

        Args:
            thread_id: The workflow thread ID
            status: New status (active, completed, expired)

        Returns:
            True if updated successfully.
        """
        thread = self._threads.get(thread_id)
        if not thread:
            return False

        thread.status = status
        thread.last_accessed_at = datetime.now(timezone.utc)
        return True

    def delete_thread(self, thread_id: str) -> bool:
        """Delete a thread metadata record.

        Args:
            thread_id: The workflow thread ID

        Returns:
            True if deleted successfully.
        """
        if thread_id in self._threads:
            del self._threads[thread_id]
            logger.info(f"Deleted thread metadata for {thread_id}")
            return True
        return False

    def get_thread(self, thread_id: str) -> Optional[dict]:
        """Get thread metadata by ID.

        Args:
            thread_id: The workflow thread ID

        Returns:
            Thread metadata dict or None if not found.
        """
        thread = self._threads.get(thread_id)
        return thread.to_dict() if thread else None

    def get_expired_threads(self, hours_old: Optional[float] = None) -> list[str]:
        """Get list of thread IDs that have expired.

        Args:
            hours_old: Override TTL - find threads not accessed in this many hours

        Returns:
            List of expired thread IDs.
        """
        now = datetime.now(timezone.utc)
        expired = []

        for thread_id, thread in self._threads.items():
            if thread.status != "active":
                continue

            if hours_old is not None:
                cutoff = now - timedelta(hours=hours_old)
                if thread.last_accessed_at < cutoff:
                    expired.append(thread_id)
            else:
                if thread.expires_at < now:
                    expired.append(thread_id)

        return expired

    def delete_checkpoint_data(self, thread_id: str) -> bool:
        """Delete checkpoint data for a thread (no-op for in-memory).

        Args:
            thread_id: The workflow thread ID

        Returns:
            True (always succeeds for in-memory).
        """
        # No-op for in-memory - checkpoint data is cleaned up with workflow
        return True

    def cleanup_expired_threads(self, hours_old: Optional[float] = None) -> dict:
        """Clean up all expired threads.

        Args:
            hours_old: Override TTL - clean threads not accessed in this many hours

        Returns:
            Dict with cleanup stats: {"deleted": N, "errors": N, "thread_ids": [...]}
        """
        expired_threads = self.get_expired_threads(hours_old)

        if not expired_threads:
            return {"deleted": 0, "errors": 0, "thread_ids": []}

        deleted = 0
        errors = 0
        deleted_ids = []

        for thread_id in expired_threads:
            try:
                if self.delete_thread(thread_id):
                    deleted += 1
                    deleted_ids.append(thread_id)
                else:
                    errors += 1
            except Exception as e:
                logger.error(f"Error cleaning up thread {thread_id}: {e}")
                errors += 1

        logger.info(f"Cleanup complete: deleted {deleted}, errors {errors}")
        return {"deleted": deleted, "errors": errors, "thread_ids": deleted_ids}

    def get_all_threads(self) -> list[dict]:
        """Get all thread metadata (for debugging/admin)."""
        return [thread.to_dict() for thread in self._threads.values()]

    def get_thread_count(self) -> int:
        """Get total number of tracked threads."""
        return len(self._threads)

    def close(self):
        """Stop cleanup task and clear data."""
        self.stop_cleanup_task()
        self._threads.clear()


# Singleton instance for use across the application
_metadata_service: Optional[ThreadMetadataService] = None


def get_metadata_service() -> ThreadMetadataService:
    """Get the singleton ThreadMetadataService instance."""
    global _metadata_service
    if _metadata_service is None:
        _metadata_service = ThreadMetadataService()
    return _metadata_service


def reset_metadata_service():
    """Reset singleton (for testing)."""
    global _metadata_service
    if _metadata_service:
        _metadata_service.close()
    _metadata_service = None
