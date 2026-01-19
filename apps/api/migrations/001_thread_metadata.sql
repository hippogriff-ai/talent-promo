-- Migration: Create thread_metadata table for tracking workflow lifecycle
-- This table tracks thread creation, access times, and expiration for cleanup

CREATE TABLE IF NOT EXISTS thread_metadata (
    thread_id TEXT PRIMARY KEY,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_accessed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE,
    user_id TEXT,  -- Future: for multi-tenant support
    status TEXT DEFAULT 'active',  -- active, completed, expired
    workflow_step TEXT,
    metadata JSONB DEFAULT '{}'
);

-- Index for cleanup queries (find expired threads)
CREATE INDEX IF NOT EXISTS idx_thread_metadata_expires
    ON thread_metadata(expires_at)
    WHERE status = 'active';

-- Index for finding threads by last access time
CREATE INDEX IF NOT EXISTS idx_thread_metadata_last_accessed
    ON thread_metadata(last_accessed_at);

-- Index for status queries
CREATE INDEX IF NOT EXISTS idx_thread_metadata_status
    ON thread_metadata(status);

-- Comment for documentation
COMMENT ON TABLE thread_metadata IS 'Tracks workflow thread lifecycle for cleanup and persistence';
COMMENT ON COLUMN thread_metadata.expires_at IS 'Calculated as created_at + TTL (default 30 days)';
COMMENT ON COLUMN thread_metadata.status IS 'active = in use, completed = finished, expired = cleaned up';
