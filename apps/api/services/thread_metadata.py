"""Thread Metadata Service for tracking workflow lifecycle.

This service manages the thread_metadata table which tracks:
- Thread creation and access times
- Thread expiration for cleanup
- Workflow status and step

Used for:
- Determining which threads to clean up
- Tracking thread activity for TTL extension
- Providing thread listing and filtering
"""

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# Default TTL for threads (30 days)
DEFAULT_TTL_DAYS = int(os.getenv("THREAD_TTL_DAYS", "30"))


class ThreadMetadataService:
    """Service for managing thread metadata in Postgres."""

    def __init__(self, database_url: Optional[str] = None):
        """Initialize the service.

        Args:
            database_url: Postgres connection string. If None, uses DATABASE_URL env var.
        """
        self.database_url = database_url or os.getenv("DATABASE_URL")
        self._connection = None

    def _get_connection(self):
        """Get or create database connection."""
        if not self.database_url:
            logger.warning("No DATABASE_URL configured, thread metadata disabled")
            return None

        if self._connection is None or self._connection.closed:
            try:
                import psycopg2
                self._connection = psycopg2.connect(self.database_url)
            except ImportError:
                logger.error("psycopg2 not installed, thread metadata disabled")
                return None
            except Exception as e:
                logger.error(f"Failed to connect to database: {e}")
                return None

        return self._connection

    def ensure_table_exists(self) -> bool:
        """Create the thread_metadata table if it doesn't exist.

        Returns:
            True if table exists or was created, False on error.
        """
        conn = self._get_connection()
        if not conn:
            return False

        try:
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS thread_metadata (
                    thread_id TEXT PRIMARY KEY,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    last_accessed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    expires_at TIMESTAMP WITH TIME ZONE,
                    user_id TEXT,
                    status TEXT DEFAULT 'active',
                    workflow_step TEXT,
                    metadata JSONB DEFAULT '{}'
                )
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_thread_metadata_expires
                ON thread_metadata(expires_at)
                WHERE status = 'active'
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_thread_metadata_last_accessed
                ON thread_metadata(last_accessed_at)
            """)
            conn.commit()
            cur.close()
            return True
        except Exception as e:
            logger.error(f"Failed to create thread_metadata table: {e}")
            conn.rollback()
            return False

    def create_thread(
        self,
        thread_id: str,
        workflow_step: str = "ingest",
        user_id: Optional[str] = None,
        ttl_days: Optional[int] = None,
    ) -> bool:
        """Create a new thread metadata record.

        Args:
            thread_id: The workflow thread ID
            workflow_step: Initial workflow step (default: ingest)
            user_id: Optional user ID for multi-tenant support
            ttl_days: Custom TTL in days (default: DEFAULT_TTL_DAYS)

        Returns:
            True if created successfully, False on error.
        """
        conn = self._get_connection()
        if not conn:
            return False

        ttl = ttl_days or DEFAULT_TTL_DAYS
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(days=ttl)

        try:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO thread_metadata
                    (thread_id, created_at, last_accessed_at, expires_at, user_id, status, workflow_step)
                VALUES (%s, %s, %s, %s, %s, 'active', %s)
                ON CONFLICT (thread_id) DO UPDATE SET
                    last_accessed_at = EXCLUDED.last_accessed_at,
                    workflow_step = EXCLUDED.workflow_step
                """,
                (thread_id, now, now, expires_at, user_id, workflow_step),
            )
            conn.commit()
            cur.close()
            logger.info(f"Created thread metadata for {thread_id}, expires {expires_at}")
            return True
        except Exception as e:
            logger.error(f"Failed to create thread metadata: {e}")
            conn.rollback()
            return False

    def update_last_accessed(self, thread_id: str, workflow_step: Optional[str] = None) -> bool:
        """Update the last_accessed_at timestamp for a thread.

        Args:
            thread_id: The workflow thread ID
            workflow_step: Optional new workflow step

        Returns:
            True if updated successfully, False on error.
        """
        conn = self._get_connection()
        if not conn:
            return False

        now = datetime.now(timezone.utc)

        try:
            cur = conn.cursor()
            # Use COALESCE to only update workflow_step if a new value is provided
            cur.execute(
                """
                UPDATE thread_metadata
                SET last_accessed_at = %s,
                    workflow_step = COALESCE(%s, workflow_step)
                WHERE thread_id = %s
                """,
                (now, workflow_step, thread_id),
            )
            conn.commit()
            cur.close()
            return True
        except Exception as e:
            logger.error(f"Failed to update thread metadata: {e}")
            conn.rollback()
            return False

    def update_status(self, thread_id: str, status: str) -> bool:
        """Update the status of a thread.

        Args:
            thread_id: The workflow thread ID
            status: New status (active, completed, expired)

        Returns:
            True if updated successfully, False on error.
        """
        conn = self._get_connection()
        if not conn:
            return False

        now = datetime.now(timezone.utc)

        try:
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE thread_metadata
                SET status = %s, last_accessed_at = %s
                WHERE thread_id = %s
                """,
                (status, now, thread_id),
            )
            conn.commit()
            cur.close()
            return True
        except Exception as e:
            logger.error(f"Failed to update thread status: {e}")
            conn.rollback()
            return False

    def delete_thread(self, thread_id: str) -> bool:
        """Delete a thread metadata record.

        Args:
            thread_id: The workflow thread ID

        Returns:
            True if deleted successfully, False on error.
        """
        conn = self._get_connection()
        if not conn:
            return False

        try:
            cur = conn.cursor()
            cur.execute(
                "DELETE FROM thread_metadata WHERE thread_id = %s",
                (thread_id,),
            )
            conn.commit()
            cur.close()
            return True
        except Exception as e:
            logger.error(f"Failed to delete thread metadata: {e}")
            conn.rollback()
            return False

    def get_thread(self, thread_id: str) -> Optional[dict]:
        """Get thread metadata by ID.

        Args:
            thread_id: The workflow thread ID

        Returns:
            Thread metadata dict or None if not found.
        """
        conn = self._get_connection()
        if not conn:
            return None

        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT thread_id, created_at, last_accessed_at, expires_at,
                       user_id, status, workflow_step, metadata
                FROM thread_metadata
                WHERE thread_id = %s
                """,
                (thread_id,),
            )
            row = cur.fetchone()
            cur.close()

            if row:
                return {
                    "thread_id": row[0],
                    "created_at": row[1].isoformat() if row[1] else None,
                    "last_accessed_at": row[2].isoformat() if row[2] else None,
                    "expires_at": row[3].isoformat() if row[3] else None,
                    "user_id": row[4],
                    "status": row[5],
                    "workflow_step": row[6],
                    "metadata": row[7] or {},
                }
            return None
        except Exception as e:
            logger.error(f"Failed to get thread metadata: {e}")
            return None

    def get_expired_threads(self, days_old: Optional[int] = None) -> list[str]:
        """Get list of thread IDs that have expired.

        Args:
            days_old: Override TTL - find threads not accessed in this many days

        Returns:
            List of expired thread IDs.
        """
        conn = self._get_connection()
        if not conn:
            return []

        try:
            cur = conn.cursor()

            if days_old is not None:
                # Find threads not accessed in X days
                cutoff = datetime.now(timezone.utc) - timedelta(days=days_old)
                cur.execute(
                    """
                    SELECT thread_id FROM thread_metadata
                    WHERE last_accessed_at < %s AND status = 'active'
                    """,
                    (cutoff,),
                )
            else:
                # Find threads past their expiration
                cur.execute(
                    """
                    SELECT thread_id FROM thread_metadata
                    WHERE expires_at < NOW() AND status = 'active'
                    """
                )

            rows = cur.fetchall()
            cur.close()
            return [row[0] for row in rows]
        except Exception as e:
            logger.error(f"Failed to get expired threads: {e}")
            return []

    def delete_checkpoint_data(self, thread_id: str) -> bool:
        """Delete LangGraph checkpoint data for a thread.

        This deletes from the LangGraph-managed tables:
        - checkpoints
        - checkpoint_writes
        - checkpoint_blobs

        Args:
            thread_id: The workflow thread ID

        Returns:
            True if deleted successfully, False on error.
        """
        conn = self._get_connection()
        if not conn:
            return False

        # LangGraph checkpoint tables to clean (hardcoded for security)
        CHECKPOINT_TABLES = ("checkpoint_blobs", "checkpoint_writes", "checkpoints")

        try:
            from psycopg2 import sql

            cur = conn.cursor()

            # Delete from all LangGraph checkpoint tables
            # These tables may not exist if using MemorySaver, so we ignore errors
            for table in CHECKPOINT_TABLES:
                try:
                    # Use psycopg2.sql for safe identifier quoting
                    cur.execute(
                        sql.SQL("DELETE FROM {} WHERE thread_id = %s").format(
                            sql.Identifier(table)
                        ),
                        (thread_id,),
                    )
                except Exception as e:
                    logger.debug(f"Could not delete from {table}: {e}")

            conn.commit()
            cur.close()
            logger.info(f"Deleted checkpoint data for thread {thread_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete checkpoint data: {e}")
            conn.rollback()
            return False

    def cleanup_expired_threads(self, days_old: Optional[int] = None) -> dict:
        """Clean up all expired threads.

        This deletes:
        - Thread metadata records
        - LangGraph checkpoint data

        Args:
            days_old: Override TTL - clean threads not accessed in this many days

        Returns:
            Dict with cleanup stats: {"deleted": N, "errors": N, "thread_ids": [...]}
        """
        expired_threads = self.get_expired_threads(days_old)

        if not expired_threads:
            return {"deleted": 0, "errors": 0, "thread_ids": []}

        deleted = 0
        errors = 0
        deleted_ids = []

        for thread_id in expired_threads:
            try:
                # Delete checkpoint data first
                self.delete_checkpoint_data(thread_id)

                # Then delete metadata
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

    def close(self):
        """Close the database connection."""
        if self._connection and not self._connection.closed:
            self._connection.close()
            self._connection = None


# Singleton instance for use across the application
_metadata_service: Optional[ThreadMetadataService] = None


def get_metadata_service() -> ThreadMetadataService:
    """Get the singleton ThreadMetadataService instance."""
    global _metadata_service
    if _metadata_service is None:
        _metadata_service = ThreadMetadataService()
        _metadata_service.ensure_table_exists()
    return _metadata_service
